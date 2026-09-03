import requests
import urllib.robotparser
import urllib.parse
import gzip
import re
import json
import time


from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

QWEN_SERVER = "http://192.168.86.243:5001/process"

OUTPUT_FILE = "website_research.json"

REQUEST_TIMEOUT = 15
QWEN_TIMEOUT = 120

MAX_SITEMAP_URLS = 10000
MAX_URL_CATALOGUE = 5000

MAX_PAGES_PER_ROUND = 4
MAX_QWEN_URLS = 120

MAX_PAGE_CHARS = 15000

MAX_SNIPPETS_PER_PAGE = 8
MAX_SNIPPET_CHARS = 700

MAX_RESEARCH_STATE_CHARS = 30000

MAX_NO_PROGRESS_ROUNDS = 2


# ============================================================
# URL HELPERS
# ============================================================

def normalize_url(url):
	if not url:
		return None

	url = str(url).strip()

	try:
		parsed = urllib.parse.urlsplit(
			url
		)

		if parsed.scheme not in (
			"http",
			"https"
		):
			return None

		if not parsed.netloc:
			return None

		path = parsed.path or "/"

		return urllib.parse.urlunsplit((
			parsed.scheme.lower(),
			parsed.netloc.lower(),
			path,
			parsed.query,
			""
		))

	except Exception:
		return None


def same_domain(
	url,
	base_url
):
	try:
		a = urllib.parse.urlsplit(
			url
		)

		b = urllib.parse.urlsplit(
			base_url
		)

		return (
			a.netloc.lower()
			== b.netloc.lower()
		)

	except Exception:
		return False


# ============================================================
# ROBOTS
# ============================================================

def get_robots_parser(
	base_url
):
	parsed = urllib.parse.urlsplit(
		base_url
	)

	robots_url = (
		f"{parsed.scheme}://"
		f"{parsed.netloc}/robots.txt"
	)

	print(
		"Checking robots.txt:"
	)

	print(
		robots_url
	)

	rp = urllib.robotparser.RobotFileParser()

	try:
		response = requests.get(
			robots_url,
			timeout=REQUEST_TIMEOUT,
			headers={
				"User-Agent":
					"EvidenceResearchBot/1.0"
			}
		)

		if response.status_code == 200:
			rp.parse(
				response.text.splitlines()
			)
		else:
			rp.parse([])

	except Exception:
		rp.parse([])

	return rp


# ============================================================
# SITEMAP DISCOVERY
# ============================================================

def discover_sitemaps(
	base_url,
	robots_parser
):
	sitemaps = []

	try:
		for sitemap in (
			robots_parser.site_maps()
			or []
		):
			sitemaps.append(
				sitemap
			)
	except Exception:
		pass

	parsed = urllib.parse.urlsplit(
		base_url
	)

	common = [
		"/sitemap.xml",
		"/sitemap.xml.gz",
		"/sitemap_index.xml",
		"/sitemap_index.xml.gz"
	]

	for path in common:
		url = urllib.parse.urlunsplit((
			parsed.scheme,
			parsed.netloc,
			path,
			"",
			""
		))

		if url not in sitemaps:
			sitemaps.append(
				url
			)

	return sitemaps


# ============================================================
# SITEMAP READING
# ============================================================

def read_sitemap(
	url
):
	print(
		f"Reading sitemap: {url}"
	)

	try:
		response = requests.get(
			url,
			timeout=REQUEST_TIMEOUT,
			headers={
				"User-Agent":
					"EvidenceResearchBot/1.0"
			}
		)

		print(
			f"  HTTP {response.status_code} | "
			f"{response.headers.get('content-type', '')}"
		)

		if response.status_code != 200:
			return []

		content = response.content

		if url.lower().endswith(
			".gz"
		):
			try:
				content = gzip.decompress(
					content
				)
			except Exception:
				return []

		text = content.decode(
			"utf-8",
			errors="ignore"
		)

		soup = BeautifulSoup(
			text,
			"xml"
		)

		locs = []

		for loc in soup.find_all(
			"loc"
		):
			value = loc.get_text(
				strip=True
			)

			if value:
				locs.append(
					value
				)

		return locs

	except Exception as e:
		print(
			"  Sitemap error:",
			e
		)

		return []


def collect_sitemap_urls(
	sitemaps
):
	queue = list(
		sitemaps
	)

	visited_sitemaps = set()
	page_urls = set()

	while (
		queue
		and len(page_urls)
		< MAX_SITEMAP_URLS
	):
		sitemap_url = normalize_url(
			queue.pop(0)
		)

		if not sitemap_url:
			continue

		if sitemap_url in visited_sitemaps:
			continue

		visited_sitemaps.add(
			sitemap_url
		)

		locs = read_sitemap(
			sitemap_url
		)

		for loc in locs:
			loc_normalized = normalize_url(
				loc
			)

			if not loc_normalized:
				continue

			lower = (
				loc_normalized.lower()
			)

			if (
				lower.endswith(".xml")
				or lower.endswith(".xml.gz")
			):
				if (
					loc_normalized
					not in visited_sitemaps
				):
					queue.append(
						loc_normalized
					)

			else:
				page_urls.add(
					loc_normalized
				)

				if (
					len(page_urls)
					>= MAX_SITEMAP_URLS
				):
					break

	return list(
		page_urls
	)


# ============================================================
# HTML CLEANING
# ============================================================

def clean_page(
	html,
	page_url
):
	soup = BeautifulSoup(
		html,
		"html.parser"
	)

	for tag in soup([
		"script",
		"style",
		"noscript",
		"svg",
		"canvas",
		"iframe",
		"template",
		"input",
		"textarea",
		"select",
		"button"
	]):
		tag.decompose()

	title = ""

	if soup.title:
		title = soup.title.get_text(
			" ",
			strip=True
		)

	meta_description = ""

	meta = soup.find(
		"meta",
		attrs={
			"name": re.compile(
				"^description$",
				re.I
			)
		}
	)

	if meta:
		meta_description = (
			meta.get("content")
			or ""
		).strip()

	generator = ""

	generator_meta = soup.find(
		"meta",
		attrs={
			"name": re.compile(
				"^generator$",
				re.I
			)
		}
	)

	if generator_meta:
		generator = (
			generator_meta.get(
				"content"
			)
			or ""
		).strip()

	headings = []

	for tag in soup.find_all([
		"h1",
		"h2",
		"h3"
	]):
		text = tag.get_text(
			" ",
			strip=True
		)

		if text:
			headings.append(
				text
			)

	links = []

	for a in soup.find_all(
		"a",
		href=True
	):
		href = a.get(
			"href"
		)

		if not href:
			continue

		absolute = urllib.parse.urljoin(
			page_url,
			href
		)

		absolute = normalize_url(
			absolute
		)

		if not absolute:
			continue

		if not same_domain(
			absolute,
			page_url
		):
			continue

		links.append(
			absolute
		)

	visible_text = soup.get_text(
		" ",
		strip=True
	)

	visible_text = re.sub(
		r"\s+",
		" ",
		visible_text
	).strip()

	return {
		"url": page_url,
		"title": title,
		"description": meta_description,
		"generator": generator,
		"headings": headings[:50],
		"text": visible_text[
			:MAX_PAGE_CHARS
		],
		"links": list(
			dict.fromkeys(
				links
			)
		)
	}


# ============================================================
# TOKENIZATION
# ============================================================

def tokenize(
	text
):
	return set(
		re.findall(
			r"[a-z0-9]+",
			str(text).lower()
		)
	)


# ============================================================
# DATE DETECTION
# ============================================================

MONTHS = (
	"january|february|march|april|may|june|"
	"july|august|september|october|november|december"
)


def contains_date(
	text
):
	lower = text.lower()

	patterns = [
		# 2026-09-02
		r"\b(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b",

		# September 2, 2026
		rf"\b(?:{MONTHS})\s+\d{{1,2}}"
		r"(?:,\s*|\s+)(?:19|20)\d{2}\b",

		# 2 September 2026
		rf"\b\d{{1,2}}\s+(?:{MONTHS})"
		r"\s+(?:19|20)\d{2}\b",

		# Sep 2, 2026
		r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|"
		r"sep|oct|nov|dec)\.?\s+\d{1,2}"
		r"(?:,\s*|\s+)(?:19|20)\d{2}\b",

		# Relative time.
		r"\b(?:today|yesterday|tomorrow)\b",

		r"\b\d+\s+(?:day|days|hour|hours|"
		r"week|weeks|month|months)\s+ago\b"
	]

	for pattern in patterns:
		if re.search(
			pattern,
			lower
		):
			return True

	return False


def extract_date(
	text
):
	patterns = [
		r"\b(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b",

		rf"\b(?:{MONTHS})\s+\d{{1,2}}"
		r"(?:,\s*|\s+)(?:19|20)\d{2}\b",

		rf"\b\d{{1,2}}\s+(?:{MONTHS})"
		r"\s+(?:19|20)\d{2}\b",

		r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|"
		r"sep|oct|nov|dec)\.?\s+\d{1,2}"
		r"(?:,\s*|\s+)(?:19|20)\d{2}\b",

		r"\b(?:today|yesterday|tomorrow)\b",

		r"\b\d+\s+(?:day|days|hour|hours|"
		r"week|weeks|month|months)\s+ago\b"
	]

	for pattern in patterns:
		match = re.search(
			pattern,
			text,
			re.I
		)

		if match:
			return match.group(0)

	return ""


# ============================================================
# RELEVANT SNIPPETS
# ============================================================

IMPORTANT_TERMS = [
	"demo",
	"test website",
	"practice",
	"scraping",
	"sandbox",
	"randomly assigned",
	"fake",
	"real",
	"about us",
	"contact",
	"privacy",
	"terms",
	"purpose",
	"latest",
	"recent",
	"recently published",
	"newest",
	"today",
	"announcement",
	"news",
	"published",
	"science",
	"scientific",
	"research",
	"discovery",
	"discoveries",
	"finding",
	"findings",
	"observation",
	"observations",
	"phenomenon",
	"phenomena"
]


def extract_relevant_snippets(
	page,
	question,
	plan
):
	text = page.get(
		"text",
		""
	)

	if not text:
		return []

	profile = plan.get(
		"research_profile",
		{}
	)

	is_recency = (
		profile.get(
			"requires_dates",
			False
		)
		or profile.get(
			"type"
		) == "recency"
	)

	requires_science = (
		profile.get(
			"requires_scientific_content",
			False
		)
	)

	question_terms = tokenize(
		question
	)

	for value in plan.get(
		"search_terms",
		[]
	):
		question_terms.update(
			tokenize(
				str(value)
			)
		)

	for value in plan.get(
		"evidence_required",
		[]
	):
		question_terms.update(
			tokenize(
				str(value)
			)
		)

	sentences = re.split(
		r"(?<=[.!?])\s+",
		text
	)

	scored = []

	for index, sentence in enumerate(
		sentences
	):
		sentence = sentence.strip()

		if len(sentence) < 20:
			continue

		lower = sentence.lower()

		terms = tokenize(
			sentence
		)

		score = 0

		score += (
			len(
				terms.intersection(
					question_terms
				)
			) * 4
		)

		for important in IMPORTANT_TERMS:
			if important in lower:
				score += 3

		has_date = contains_date(
			sentence
		)

		if has_date:
			score += 8

			if is_recency:
				score += 12

		if requires_science:
			science_terms = [
				"science",
				"scientific",
				"research",
				"discovery",
				"discoveries",
				"finding",
				"findings",
				"observation",
				"observations",
				"phenomenon",
				"phenomena",
				"experiment",
				"experiment",
				"study",
				"mission",
				"space",
				"planet",
				"galaxy",
				"universe",
				"moon",
				"mars",
				"asteroid",
				"telescope"
			]

			for term in science_terms:
				if term in lower:
					score += 5

		# Keep surrounding sentence context for dated articles.
		if is_recency and has_date:
			score += 10

			if index > 0:
				previous = sentences[
					index - 1
				].strip()

				if len(previous) > 20:
					score += 3

		scored.append(
			(
				score,
				index,
				sentence
			)
		)

	scored.sort(
		key=lambda item: item[0],
		reverse=True
	)

	results = []

	used = set()

	for score, index, sentence in scored:
		if index in used:
			continue

		used.add(
			index
		)

		if len(sentence) > MAX_SNIPPET_CHARS:
			sentence = (
				sentence[
					:MAX_SNIPPET_CHARS
				]
				+ "..."
			)

		results.append(
			sentence
		)

		if len(results) >= MAX_SNIPPETS_PER_PAGE:
			break

	# For recency tasks, make sure date-bearing sentences are retained
	# even if semantic scoring accidentally pushed them down.
	if is_recency:
		for index, sentence in enumerate(
			sentences
		):
			if not contains_date(
				sentence
			):
				continue

			sentence = sentence.strip()

			if len(sentence) < 20:
				continue

			if sentence in results:
				continue

			if len(sentence) > MAX_SNIPPET_CHARS:
				sentence = (
					sentence[
						:MAX_SNIPPET_CHARS
					]
					+ "..."
				)

			results.append(
				sentence
			)

			if len(results) >= MAX_SNIPPETS_PER_PAGE:
				break

	return results


# ============================================================
# ARTICLE / HEADING EVIDENCE
# ============================================================

def build_page_evidence(
	page,
	question,
	plan
):
	snippets = extract_relevant_snippets(
		page,
		question,
		plan
	)

	profile = plan.get(
		"research_profile",
		{}
	)

	is_recency = (
		profile.get(
			"type"
		) == "recency"
		or profile.get(
			"requires_dates",
			False
		)
	)

	headings = page.get(
		"headings",
		[]
	)

	evidence = {
		"url": page.get(
			"url"
		),
		"title": page.get(
			"title"
		),
		"description": page.get(
			"description"
		),
		"headings": headings[:20],
		"snippets": snippets
	}

	if is_recency:
		dated_evidence = []

		for heading in headings:
			if contains_date(
				heading
			):
				dated_evidence.append({
					"text": heading,
					"date": extract_date(
						heading
					)
				})

		for snippet in snippets:
			date = extract_date(
				snippet
			)

			if date:
				dated_evidence.append({
					"text": snippet,
					"date": date
				})

		evidence[
			"dated_evidence"
		] = dated_evidence[:12]

	return evidence


# ============================================================
# URL SCORING
# ============================================================

def score_url(
	url,
	question,
	plan
):
	lower = url.lower()

	score = 0

	question_terms = tokenize(
		question
	)

	search_terms = set()

	for term in plan.get(
		"search_terms",
		[]
	):
		search_terms.update(
			tokenize(
				str(term)
			)
		)

	all_terms = (
		question_terms
		.union(search_terms)
	)

	for term in all_terms:
		if len(term) < 3:
			continue

		if term in lower:
			score += 5

	profile = plan.get(
		"research_profile",
		{}
	)

	profile_type = profile.get(
		"type",
		"general"
	)

	# --------------------------------------------------------
	# General useful pages
	# --------------------------------------------------------

	boosts = {
		"/about": 10,
		"/contact": 8,
		"/privacy": 6,
		"/terms": 6,
		"/faq": 8,
		"/demo": 10,
		"/test": 8,
		"/practice": 8,
		"/documentation": 8,
		"/project": 6,
		"/scrape": 7,
		"/sandbox": 8
	}

	for path, points in boosts.items():
		if path in lower:
			score += points

	# --------------------------------------------------------
	# Recency
	# --------------------------------------------------------

	if (
		profile_type
		== "recency"
	):
		recency_boosts = {
			"/news": 20,
			"/recent": 20,
			"/recently-published": 25,
			"/latest": 23,
			"/announcements": 18,
			"/press": 15,
			"/updates": 15,
			"/events": 10,
			"/activities": 15,
			"/activity": 15,
			"/research": 12,
			"/science": 12,
			"/discoveries": 14,
			"/discovery": 14,
			"/findings": 14,
			"/blog": 10,
			"/stories": 10
		}

		for path, points in recency_boosts.items():
			if path in lower:
				score += points

		for word in [
			"recent",
			"latest",
			"newest",
			"published",
			"announcement",
			"update",
			"news",
			"research",
			"science",
			"discovery",
			"finding"
		]:
			if word in lower:
				score += 8

	# --------------------------------------------------------
	# Scientific content
	# --------------------------------------------------------

	if profile.get(
		"requires_scientific_content",
		False
	):
		for word in [
			"science",
			"scientific",
			"research",
			"discovery",
			"discoveries",
			"finding",
			"findings",
			"experiment",
			"study",
			"mission",
			"observatory",
			"telescope"
		]:
			if word in lower:
				score += 7

	# --------------------------------------------------------
	# Product/catalogue penalty
	# --------------------------------------------------------

	for path in [
		"/catalogue/",
		"/catalog/",
		"/product/",
		"/products/"
	]:
		if path in lower:
			score -= 25

	# --------------------------------------------------------
	# Pagination penalty
	# --------------------------------------------------------

	if re.search(
		r"/page[-_/]?\d+",
		lower
	):
		score -= 8

	if re.search(
		r"[?&](?:page|p)=\d+",
		lower
	):
		score -= 8

	# --------------------------------------------------------
	# Homepage
	# --------------------------------------------------------

	parsed = urllib.parse.urlsplit(
		url
	)

	if parsed.path in (
		"",
		"/"
	):
		score += 6

	return score


# ============================================================
# QWEN URL LIST
# ============================================================

def build_qwen_url_list(
	available_urls,
	downloaded_urls,
	question,
	plan,
	max_urls=MAX_QWEN_URLS
):
	downloaded_set = set(
		downloaded_urls
	)

	candidates = []

	for raw_url in available_urls:
		url = normalize_url(
			raw_url
		)

		if not url:
			continue

		if url in downloaded_set:
			continue

		score = score_url(
			url,
			question,
			plan
		)

		candidates.append(
			(
				score,
				url
			)
		)

	candidates.sort(
		key=lambda item: (
			item[0],
			len(item[1])
		),
		reverse=True
	)

	return [
		url
		for score, url
		in candidates[:max_urls]
	]


# ============================================================
# RESEARCH STATE
# ============================================================

def build_research_state(
	question,
	plan,
	pages,
	available_urls,
	downloaded_urls,
	rejected_requests,
	download_history
):
	page_summaries = []

	for page in pages:
		page_summaries.append(
			build_page_evidence(
				page,
				question,
				plan
			)
		)

	available_for_qwen = (
		build_qwen_url_list(
			available_urls,
			downloaded_urls,
			question,
			plan
		)
	)

	state = {
		"downloaded_pages": list(
			downloaded_urls
		),
		"pages": page_summaries,
		"available_urls": available_for_qwen,
		"rejected_requests":
			rejected_requests[-40:],
		"download_history":
			download_history[-20:]
	}

	encoded = json.dumps(
		state,
		ensure_ascii=False
	)

	if len(encoded) > MAX_RESEARCH_STATE_CHARS:
		state[
			"available_urls"
		] = state[
			"available_urls"
		][:70]

	encoded = json.dumps(
		state,
		ensure_ascii=False
	)

	if len(encoded) > MAX_RESEARCH_STATE_CHARS:
		state[
			"pages"
		] = state[
			"pages"
		][:20]

	return state


# ============================================================
# QWEN HTTP
# ============================================================

def call_qwen(
	payload
):
	try:
		response = requests.post(
			QWEN_SERVER,
			json=payload,
			timeout=QWEN_TIMEOUT
		)

		response.raise_for_status()

		return response.json()

	except Exception as e:
		print(
			"Qwen request failed:",
			e
		)

		return None


# ============================================================
# PAGE DOWNLOAD
# ============================================================

def download_page(
	url,
	robots_parser
):
	try:
		if not robots_parser.can_fetch(
			"EvidenceResearchBot",
			url
		):
			print(
				f"  BLOCKED BY ROBOTS: {url}"
			)

			return None

	except Exception:
		pass

	try:
		response = requests.get(
			url,
			timeout=REQUEST_TIMEOUT,
			headers={
				"User-Agent":
					"EvidenceResearchBot/1.0"
			}
		)

		if response.status_code != 200:
			print(
				f"  HTTP {response.status_code}: "
				f"{url}"
			)

			return None

		content_type = (
			response.headers.get(
				"content-type",
				""
			).lower()
		)

		if (
			"text/html"
			not in content_type
			and "application/xhtml"
			not in content_type
		):
			print(
				f"  NOT HTML: {url}"
			)

			return None

		return clean_page(
			response.text,
			url
		)

	except Exception as e:
		print(
			f"  ERROR: {url} -> {e}"
		)

		return None


# ============================================================
# CHALLENGE DETECTION
# ============================================================

def looks_like_challenge(
	page
):
	text = page.get(
		"text",
		""
	).lower()

	title = page.get(
		"title",
		""
	).lower()

	challenge_terms = [
		"verify you are human",
		"checking your browser",
		"just a moment",
		"enable javascript and cookies",
		"security check",
		"access denied",
		"captcha"
	]

	for term in challenge_terms:
		if (
			term in text
			or term in title
		):
			return True

	return False


# ============================================================
# DOWNLOAD REQUESTED PAGES
# ============================================================

def download_requested_pages(
	requested_urls,
	available_urls,
	downloaded_urls,
	pages,
	rejected_requests,
	download_history,
	robots_parser
):
	available_set = set(
		normalize_url(url)
		for url in available_urls
		if normalize_url(url)
	)

	downloaded_set = set(
		downloaded_urls
	)

	valid_requests = []

	for raw_url in requested_urls:
		url = normalize_url(
			raw_url
		)

		if not url:
			rejected_requests.append({
				"url": str(raw_url),
				"reason": "Invalid URL."
			})

			continue

		if url in downloaded_set:
			rejected_requests.append({
				"url": url,
				"reason":
					"Already downloaded and inspected."
			})

			continue

		if url not in available_set:
			rejected_requests.append({
				"url": url,
				"reason":
					"URL is not in the available URL catalogue."
			})

			continue

		if url in valid_requests:
			continue

		valid_requests.append(
			url
		)

		if (
			len(valid_requests)
			>= MAX_PAGES_PER_ROUND
		):
			break

	print()
	print(
		f"Downloading {len(valid_requests)} "
		"Qwen-selected pages..."
	)

	new_pages = []

	for url in valid_requests:
		print(
			f"  Downloading: {url}"
		)

		page = download_page(
			url,
			robots_parser
		)

		if page is None:
			rejected_requests.append({
				"url": url,
				"reason": "Download failed."
			})

			continue

		if looks_like_challenge(
			page
		):
			print(
				f"  CHALLENGE PAGE: {url}"
			)

			rejected_requests.append({
				"url": url,
				"reason":
					"Challenge/access-verification page."
			})

			continue

		pages.append(
			page
		)

		downloaded_urls.append(
			url
		)

		new_pages.append(
			page
		)

		download_history.append({
			"url": url,
			"time": time.time()
		})

		print(
			f"  OK: {url}"
		)

	downloaded_urls[:] = list(
		dict.fromkeys(
			downloaded_urls
		)
	)

	return new_pages


# ============================================================
# FALLBACK URL SELECTION
# ============================================================

def select_fallback_urls(
	available_urls,
	downloaded_urls,
	question,
	plan,
	count=2
):
	"""
	If Qwen says "continue" but accidentally supplies no pages,
	the Pi chooses the highest-ranked unused URLs.

	This is a safety net, not the main research decision-maker.
	"""

	urls = build_qwen_url_list(
		available_urls,
		downloaded_urls,
		question,
		plan,
		max_urls=MAX_QWEN_URLS
	)

	return urls[:count]


# ============================================================
# MAIN
# ============================================================

def main():
	print("=" * 70)
	print(
		"PI 5 EVIDENCE-FIRST AI WEBSITE RESEARCHER"
	)
	print("=" * 70)
	print()

	website = input(
		"Website URL:\n> "
	).strip()

	question = input(
		"\nWhat do you want to know?\n> "
	).strip()

	website = normalize_url(
		website
	)

	if not website:
		print(
			"Invalid website URL."
		)
		return

	start_time = time.time()

	print()
	print("=" * 70)

	# --------------------------------------------------------
	# ROBOTS
	# --------------------------------------------------------

	robots_parser = get_robots_parser(
		website
	)

	# --------------------------------------------------------
	# SITEMAPS
	# --------------------------------------------------------

	print()
	print(
		"Discovering sitemaps..."
	)

	sitemaps = discover_sitemaps(
		website,
		robots_parser
	)

	sitemap_urls = (
		collect_sitemap_urls(
			sitemaps
		)
	)

	print()
	print(
		"Cleaning sitemap URL catalogue..."
	)

	sitemap_urls = [
		url
		for url in sitemap_urls
		if same_domain(
			url,
			website
		)
	]

	if (
		len(sitemap_urls)
		> MAX_SITEMAP_URLS
	):
		sitemap_urls = sitemap_urls[
			:MAX_SITEMAP_URLS
		]

	print(
		f"Sitemap URLs: "
		f"{len(sitemap_urls)}"
	)

	available_urls = set(
		sitemap_urls
	)

	available_urls.add(
		website
	)

	print(
		f"Useful URLs: "
		f"{len(sitemap_urls)}"
	)

	# --------------------------------------------------------
	# HOMEPAGE
	# --------------------------------------------------------

	print()
	print(
		"Downloading homepage..."
	)

	homepage = download_page(
		website,
		robots_parser
	)

	if homepage is None:
		print(
			"Could not download homepage."
		)
		return

	if looks_like_challenge(
		homepage
	):
		print(
			"Homepage appears to be a challenge page."
		)
		return

	pages = [
		homepage
	]

	downloaded_urls = [
		website
	]

	download_history = [
		{
			"url": website,
			"time": time.time()
		}
	]

	rejected_requests = []

	before_discovery = len(
		available_urls
	)

	for link in homepage.get(
		"links",
		[]
	):
		available_urls.add(
			link
		)

	print(
		f"Homepage discovered "
		f"{len(available_urls) - before_discovery} "
		f"new URLs."
	)

	if (
		len(available_urls)
		> MAX_URL_CATALOGUE
	):
		available_urls = set(
			list(available_urls)[
				:MAX_URL_CATALOGUE
			]
		)

	print()
	print(
		f"Clean URL catalogue: "
		f"{len(available_urls)}"
	)

	# --------------------------------------------------------
	# PLANNER
	# --------------------------------------------------------

	print()
	print("=" * 70)
	print(
		"QWEN RESEARCH PLANNER"
	)
	print("=" * 70)

	plan = call_qwen({
		"mode": "planner",
		"question": question,
		"homepage_text": homepage.get(
			"text",
			""
		)
	})

	if not plan:
		print(
			"Planner failed."
		)
		return

	print(
		json.dumps(
			plan,
			indent=2,
			ensure_ascii=False
		)
	)

	original_objective = plan.get(
		"objective",
		question
	)

	print()
	print(
		"Immutable research objective:"
	)

	print(
		original_objective
	)

	# --------------------------------------------------------
	# RESEARCH LOOP
	# --------------------------------------------------------

	no_progress_rounds = 0
	round_number = 0

	while True:
		round_number += 1

		print()
		print("=" * 70)
		print(
			f"RESEARCH ROUND {round_number}"
		)
		print("=" * 70)

		research_state = (
			build_research_state(
				question,
				plan,
				pages,
				list(available_urls),
				downloaded_urls,
				rejected_requests,
				download_history
			)
		)

		decision = call_qwen({
			"mode": "researcher",
			"question": question,
			"plan": plan,
			"research_state": research_state
		})

		if not decision:
			print(
				"Researcher failed."
			)
			break

		print()
		print(
			"Qwen decision:"
		)

		print(
			json.dumps(
				decision,
				indent=2,
				ensure_ascii=False
			)
		)

		action = decision.get(
			"action"
		)

		# ----------------------------------------------------
		# FINAL
		# ----------------------------------------------------

		if action == "final":
			print()
			print(
				"Qwen believes the evidence "
				"is sufficient."
			)
			break

		# ----------------------------------------------------
		# STOP
		# ----------------------------------------------------

		if action == "stop_insufficient":
			print()
			print(
				"Research stopped because "
				"no useful evidence path remains."
			)
			break

		# ----------------------------------------------------
		# CONTINUE
		# ----------------------------------------------------

		if action != "continue":
			print(
				"Unknown research action."
			)
			break

		tactics = decision.get(
			"tactics",
			{}
		)

		if not isinstance(
			tactics,
			dict
		):
			tactics = {}

		for key in [
			"preferred_page_types",
			"search_terms",
			"rules"
		]:
			value = tactics.get(
				key
			)

			if isinstance(
				value,
				list
			):
				plan[key] = value

		# Never let researcher mutate objective.
		plan["objective"] = (
			original_objective
		)

		requested_pages = decision.get(
			"pages",
			[]
		)

		if not isinstance(
			requested_pages,
			list
		):
			requested_pages = []

		# ----------------------------------------------------
		# FALLBACK
		# ----------------------------------------------------

		if len(requested_pages) == 0:
			print()
			print(
				"Qwen requested continuation "
				"but selected 0 pages."
			)

			print(
				"Selecting fallback pages "
				"from the highest-ranked unused URLs..."
			)

			fallback = select_fallback_urls(
				available_urls,
				downloaded_urls,
				question,
				plan,
				count=2
			)

			if fallback:
				print(
					"Fallback pages:"
				)

				for url in fallback:
					print(
						f"  {url}"
					)

				requested_pages = fallback

				rejected_requests.append({
					"url": "[QWEN]",
					"reason":
						"Researcher returned continue with "
						"no selected pages; Pi supplied ranked "
						"fallback URLs."
				})

			else:
				print(
					"No unused URLs remain."
				)

				no_progress_rounds += 1

				if (
					no_progress_rounds
					>= MAX_NO_PROGRESS_ROUNDS
				):
					print(
						"Stopping research."
					)
					break

				continue

		# ----------------------------------------------------
		# NORMALIZE REQUESTS
		# ----------------------------------------------------

		requested_pages_normalized = []

		for url in requested_pages:
			normalized = normalize_url(
				url
			)

			if normalized:
				requested_pages_normalized.append(
					normalized
				)

		print()
		print(
			f"Qwen requested: "
			f"{len(requested_pages_normalized)} pages"
		)

		# ----------------------------------------------------
		# DOWNLOAD
		# ----------------------------------------------------

		before_page_count = len(
			pages
		)

		before_url_count = len(
			available_urls
		)

		new_pages = (
			download_requested_pages(
				requested_pages_normalized,
				list(available_urls),
				downloaded_urls,
				pages,
				rejected_requests,
				download_history,
				robots_parser
			)
		)

		# ----------------------------------------------------
		# DISCOVER NEW URLS
		# ----------------------------------------------------

		new_urls = 0

		for page in new_pages:
			for link in page.get(
				"links",
				[]
			):
				if link not in available_urls:
					available_urls.add(
						link
					)

					new_urls += 1

		if (
			len(available_urls)
			> MAX_URL_CATALOGUE
		):
			available_urls = set(
				list(available_urls)[
					:MAX_URL_CATALOGUE
				]
			)

		print()
		print(
			f"New pages discovered: "
			f"{new_urls}"
		)

		# ----------------------------------------------------
		# PROGRESS
		# ----------------------------------------------------

		page_progress = (
			len(pages)
			> before_page_count
		)

		url_progress = (
			len(available_urls)
			> before_url_count
		)

		real_progress = (
			page_progress
			or url_progress
			or new_urls > 0
		)

		if real_progress:
			no_progress_rounds = 0

			print(
				"Research made progress."
			)

		else:
			no_progress_rounds += 1

			print(
				"No new pages downloaded."
			)

			print(
				f"No-progress rounds: "
				f"{no_progress_rounds} / "
				f"{MAX_NO_PROGRESS_ROUNDS}"
			)

		if (
			no_progress_rounds
			>= MAX_NO_PROGRESS_ROUNDS
		):
			print()
			print(
				"Research has stopped because "
				"there is no longer a useful "
				"path to new evidence."
			)
			break

	# --------------------------------------------------------
	# BUILD FINAL EVIDENCE
	# --------------------------------------------------------

	final_evidence = []

	for page in pages:
		evidence = build_page_evidence(
			page,
			question,
			plan
		)

		# Include full text for final answer,
		# but keep it bounded.
		evidence["text"] = page.get(
			"text",
			""
		)[:MAX_PAGE_CHARS]

		final_evidence.append(
			evidence
		)

	# --------------------------------------------------------
	# FINAL ANSWER
	# --------------------------------------------------------

	print()
	print("=" * 70)
	print(
		"FINAL ANSWER"
	)
	print("=" * 70)

	final_result = call_qwen({
		"mode": "final",
		"question": question,
		"plan": plan,
		"evidence": final_evidence
	})

	if not final_result:
		final_result = {
			"answer":
				"Unable to obtain a final answer.",
			"confidence": "low",
			"evidence": []
		}

	print()

	print(
		final_result.get(
			"answer",
			""
		)
	)

	print()
	print(
		"Confidence:",
		final_result.get(
			"confidence",
			"low"
		)
	)

	evidence = final_result.get(
		"evidence",
		[]
	)

	if evidence:
		print()
		print(
			"Evidence:"
		)

		for item in evidence:
			if not isinstance(
				item,
				dict
			):
				continue

			print(
				f" - {item.get('url', '')}"
			)

			fact = item.get(
				"fact",
				""
			)

			if fact:
				print(
					f"   {fact}"
				)

			date = item.get(
				"date",
				""
			)

			if date:
				print(
					f"   Date: {date}"
				)

	# --------------------------------------------------------
	# SAVE
	# --------------------------------------------------------

	output = {
		"website": website,
		"question": question,
		"objective": original_objective,
		"plan": plan,
		"answer": final_result,
		"pages": pages,
		"downloaded_urls":
			downloaded_urls,
		"available_urls":
			list(available_urls),
		"rejected_requests":
			rejected_requests,
		"download_history":
			download_history,
		"research_rounds":
			round_number
	}

	with open(
		OUTPUT_FILE,
		"w",
		encoding="utf-8"
	) as f:
		json.dump(
			output,
			f,
			indent=2,
			ensure_ascii=False
		)

	elapsed = (
		time.time()
		- start_time
	)

	print()
	print(
		f"Saved: {OUTPUT_FILE}"
	)

	print(
		f"Total runtime: "
		f"{elapsed:.1f} seconds"
	)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
	try:
		main()

	except KeyboardInterrupt:
		print()
		print(
			"Stopped."
		)

	except Exception as e:
		print()
		print(
			"FATAL ERROR:",
			repr(e)
		)