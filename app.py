import logging
import re
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request
from wordcloud import STOPWORDS, WordCloud

matplotlib.use("Agg")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

STATIC_IMAGES_DIR = Path("static/images")
MAX_THREAD_WORKERS = 5
POSITIVE_RATINGS = {3, 4, 5}
NEGATIVE_RATINGS = {1, 2}
REQUEST_TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.3"
)


def clean_review(text: str) -> str:
    slang_map = {
        "osm": "awesome",
        "nyc": "nice",
        "thanku": "thanks",
        "superb": "super",
    }
    text = re.sub(r"[^a-zA-Z ]", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.replace("READ MORE", "")
    text = text.lower()
    words = text.split()
    words = [slang_map.get(w, w) if len(w) < 3 else w for w in words]
    return " ".join(words)


def fetch_reviews_page(
    url: str, max_reviews: int
) -> tuple[list[str], list[str], list[str], list[str], list[int], int]:
    clean_reviews: list[str] = []
    org_reviews: list[str] = []
    customer_names: list[str] = []
    comment_heads: list[str] = []
    ratings: list[int] = []
    page_number = 1
    total_fetched = 0

    while True:
        page_url = f"{url}&page={page_number}"
        try:
            resp = requests.get(
                page_url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Failed to fetch page %s: %s", page_url, e)
            return (
                clean_reviews, org_reviews, customer_names,
                comment_heads, ratings, total_fetched,
            )

        soup = BeautifulSoup(resp.content, "html.parser")
        reviews = soup.find_all("div", {"class": "_1AtVbE"})
        commentheads_ = soup.find_all("p", {"class": "_2-N8zT"})
        customernames_ = soup.find_all("p", {"class": "_2sc7ZR"})
        ratings_ = soup.find_all("div", {"class": "_3LWZlK"})

        if not reviews:
            break

        for review in reviews:
            x = review.get_text()
            org_reviews.append(x.replace("READ MORE", ""))
            clean_reviews.append(clean_review(x))

        customer_names.extend(f"~{cn.get_text()}" for cn in customernames_)
        comment_heads.extend(ch.get_text() for ch in commentheads_)

        for r in ratings_:
            try:
                val = int(r.get_text())
                if 1 <= val <= 5:
                    ratings.append(val)
                else:
                    ratings.append(0)
            except ValueError:
                ratings.append(0)

        total_fetched += len(reviews)
        if total_fetched >= max_reviews:
            break

        page_number += 1

    return (
        clean_reviews, org_reviews, customer_names,
        comment_heads, ratings, total_fetched,
    )


type ReviewDict = dict[str, Any]


def classify_sentiment(stars: int) -> str:
    if stars == 0:
        return "UNKNOWN"
    return "POSITIVE" if stars in POSITIVE_RATINGS else "NEGATIVE"


class CleanCache:
    def __init__(self, directory: str | Path) -> None:
        self.clean_path = Path(directory)
        self.clean()

    def clean(self) -> None:
        if not self.clean_path.is_dir():
            logger.warning("Directory %s does not exist", self.clean_path)
            return
        for file_path in self.clean_path.iterdir():
            if file_path.is_file():
                file_path.unlink()
                logger.info("Removed %s", file_path)


@app.route("/")
def home() -> str:
    return render_template("home.html")


@app.route("/results", methods=["GET"])
def result() -> str:
    url = request.args.get("url", "")
    try:
        nreviews = int(request.args.get("num", "10"))
    except ValueError:
        return render_template(
            "error.html",
            message="Invalid number of reviews.",
        )

    if not url:
        return render_template("error.html", message="No URL provided.")

    logger.info("Fetching URL: %s", url)

    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch product page: %s", e)
        return render_template(
            "error.html",
            message=(
                "Error fetching the URL. "
                "Please check the URL and try again."
            ),
        )

    soup = BeautifulSoup(resp.content, "html.parser")
    name_el = soup.find_all("span", {"class": "B_NuCI"})
    price_el = soup.find_all("div", {"class": "_30jeq3 _16Jk6d"})
    proname = (
        name_el[0].get_text() if name_el else "Product Name Not Found"
    )
    price = (
        price_el[0].get_text() if price_el else "Price Not Found"
    )

    all_reviews_link = soup.find_all("div", {"class": "col JOpGWq"})
    if not all_reviews_link:
        return render_template(
            "error.html",
            message="Error extracting reviews link. Please try again.",
        )

    link_el = all_reviews_link[0].find_all("a")
    if not link_el:
        return render_template(
            "error.html",
            message="Error extracting reviews link. Please try again.",
        )

    all_reviews_url = "https://www.flipkart.com" + link_el[-1].get("href", "")
    logger.info("Fetching reviews from: %s", all_reviews_url)

    start_time = time.time()
    clean_reviews: list[str] = []
    org_reviews: list[str] = []
    customer_names: list[str] = []
    comment_heads: list[str] = []
    ratings: list[int] = []
    num_reviews = 0

    with ThreadPoolExecutor(max_workers=MAX_THREAD_WORKERS) as executor:
        futures = {
            executor.submit(
                fetch_reviews_page, all_reviews_url, nreviews
            ): i
            for i in range(1, MAX_THREAD_WORKERS + 1)
        }
        for future in as_completed(futures):
            cr, o_, cn, ch, ra, count = future.result()
            clean_reviews.extend(cr)
            org_reviews.extend(o_)
            customer_names.extend(cn)
            comment_heads.extend(ch)
            ratings.extend(ra)
            num_reviews += count
            if count:
                logger.info(
                    "Fetched %d reviews. Total: %d",
                    count,
                    num_reviews,
                )

    elapsed = time.time() - start_time
    logger.info("Time to fetch reviews: %.2f seconds", elapsed)

    clean_reviews = clean_reviews[:num_reviews]
    org_reviews = org_reviews[:num_reviews]
    customer_names = customer_names[:num_reviews]
    comment_heads = comment_heads[:num_reviews]
    ratings = ratings[:num_reviews]

    wc_start = time.time()
    text = " ".join(clean_reviews)
    wc = WordCloud(
        width=1400,
        height=800,
        stopwords=set(STOPWORDS),
        background_color="white",
    ).generate(text)

    plt.figure(figsize=(20, 10), facecolor="k", edgecolor="k")
    plt.imshow(wc, interpolation="bicubic")
    plt.axis("off")
    plt.tight_layout(pad=0)

    CleanCache(STATIC_IMAGES_DIR)
    plt.savefig(STATIC_IMAGES_DIR / "woc.png")
    plt.close()
    logger.info(
        "Time to generate word cloud: %.2f seconds",
        time.time() - wc_start,
    )

    reviews_data: list[ReviewDict] = [
        {
            "review": org_reviews[i],
            "cn": customer_names[i],
            "ch": comment_heads[i],
            "stars": ratings[i],
        }
        for i in range(len(org_reviews))
    ]

    for item in reviews_data:
        item["sent"] = classify_sentiment(item["stars"])

    positive_count = sum(1 for d in reviews_data if d["sent"] == "POSITIVE")
    negative_count = sum(1 for d in reviews_data if d["sent"] == "NEGATIVE")

    return render_template(
        "result.html",
        dic=reviews_data,
        n=num_reviews,
        nn=negative_count,
        np=positive_count,
        proname=proname,
        price=price,
    )


@app.route("/wc")
def wordcloud() -> str:
    return render_template("wc.html")


if __name__ == "__main__":
    ssl._create_default_https_context = ssl._create_unverified_context
    app.run(host="127.0.0.1", port=3000, debug=True, threaded=True)
