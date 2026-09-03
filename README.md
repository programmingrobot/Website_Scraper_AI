# Website Scraper AI

Website Scraper AI is an evidence-first research crawler for a single website. It reads robots.txt, discovers sitemap URLs, downloads allowed HTML pages, cleans page text, extracts headings, links, dates, and snippets, then asks a local Qwen AI server to plan research and produce a sourced final answer.

The finished run is saved to `website_research.json` with the website, question, plan, answer, downloaded pages, discovered URLs, rejected requests, and research history.

## What It Does

- Checks `robots.txt` before downloading pages.
- Discovers sitemap files from `robots.txt` and common sitemap paths.
- Handles normal `.xml` and compressed `.xml.gz` sitemaps.
- Builds a same-domain URL catalogue.
- Downloads and cleans HTML pages with Beautiful Soup.
- Removes scripts, styles, forms, iframes, SVG, canvas, and other noisy page elements.
- Scores and selects useful URLs for the research question.
- Sends research planning, URL selection, and final-answer prompts to a local Qwen endpoint.
- Prints the final answer, confidence level, and evidence URLs.
- Saves all run data to JSON for later inspection.

## Requirements

- Python 3.10 or newer. The current local environment was tested with Python 3.13.
- A running Qwen-compatible local HTTP server.
- Internet access for the target website and for first-time dependency installation.

Python packages:

- `requests`
- `beautifulsoup4`
- `lxml`

The default Qwen endpoint is set inside `main.py` and `AI_server.py`:

```python
QWEN_SERVER = "http://192.168.86.243:5001/process"
```

Change this value if your Qwen server runs on a different host or port. The endpoint should accept JSON `POST` requests and return JSON responses.

## Download And Storage Sizes

Approximate sizes vary by operating system, CPU architecture, Python version, and package wheel availability.

| Item | Approximate size |
| --- | ---: |
| Repository source files | Less than 1 MB |
| Python installer, Windows | 25-35 MB |
| Python installer, macOS | 35-55 MB |
| Python packages downloaded by `pip` | 5-20 MB |
| Created virtual environment after install | 25-80 MB |
| Current local `venv/` size | About 30 MB |
| Typical `website_research.json` output | Depends on site size; often 100 KB to 20+ MB |

The virtual environment is not committed to Git. Each user recreates it locally from `requirements.txt`.

## Setup On Windows

1. Install Python 3 from <https://www.python.org/downloads/windows/>.
2. During installation, enable **Add python.exe to PATH** if available.
3. Clone or download this repository.
4. Start your local Qwen server.
5. Edit `QWEN_SERVER` in `main.py` if needed.
6. Double-click `run.bat`, or run this from Command Prompt:

```bat
run.bat
```

The script creates `venv`, installs dependencies, and starts the researcher.

## Setup On macOS

1. Install Python 3 from <https://www.python.org/downloads/macos/> or with Homebrew:

```sh
brew install python
```

2. Clone or download this repository.
3. Start your local Qwen server.
4. Edit `QWEN_SERVER` in `main.py` if needed.
5. Run:

```sh
chmod +x run.sh
./run.sh
```

## Setup On Linux

Install Python and virtual environment support:

```sh
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

Then run:

```sh
chmod +x run.sh
./run.sh
```

On Fedora:

```sh
sudo dnf install python3 python3-pip
chmod +x run.sh
./run.sh
```

On Arch Linux:

```sh
sudo pacman -S python python-pip
chmod +x run.sh
./run.sh
```

## Manual Setup

Use these commands if you prefer not to use the launch scripts:

```sh
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
venv/bin/python main.py
```

On Windows Command Prompt:

```bat
py -3 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe main.py
```

## How To Use

When the program starts, enter:

1. The website URL to research.
2. The question you want answered from that website.

Example:

```text
Website URL:
> https://example.com

What do you want to know?
> What services does this company offer?
```

The program will crawl allowed pages, ask Qwen to guide the research, print the final answer, and write `website_research.json`.

## Notes And Limits

- This tool researches one website at a time.
- It only downloads same-domain HTML pages.
- It skips pages blocked by `robots.txt`.
- It may stop if a page appears to be a CAPTCHA, browser check, or access-denied challenge.
- Large websites are bounded by internal limits such as maximum sitemap URLs, downloaded pages per round, text per page, and Qwen URL list size.
- Results depend on the quality and availability of the target website and the local Qwen server.

## Project Files

- `main.py` - Main interactive research crawler.
- `AI_server.py` - Duplicate/alternate entrypoint kept with the current project source.
- `requirements.txt` - Python dependencies.
- `run.sh` - macOS/Linux launcher.
- `run.bat` - Windows launcher.

## GitHub Setup Used For This Repo

```sh
git init
git remote add origin https://github.com/programmingrobot/Website_Scraper_AI
git add .
git commit -m "Initial Commit"
```
