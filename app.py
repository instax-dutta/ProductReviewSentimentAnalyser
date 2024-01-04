import re
import os
import requests
import numpy as np
from bs4 import BeautifulSoup
import urllib.request as urllib
import matplotlib
matplotlib.use('Agg')  # Set the Agg backend
import matplotlib.pyplot as plt
from nltk.corpus import stopwords
from wordcloud import WordCloud, STOPWORDS
from flask import Flask, render_template, request
import time
import concurrent.futures
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


# Function for cleaning the fetched reviews
def clean_review(x):
    x = re.sub(r'[^a-zA-Z ]', ' ', x)
    x = re.sub(r'\s+', ' ', x)
    x = re.sub(r'READ MORE', '', x)
    x = x.lower()
    x = x.split()
    y = [i if len(i) < 3 else 'awesome' if i == 'osm' else 'nice' if i == 'nyc' else 'thanks' if i == 'thanku' else
         'super' if i == 'superb' else i for i in x]
    return ' '.join(y)


# Function for extraction of the reviews
def extract_all_reviews(url, clean_reviews, org_reviews, customernames, commentheads, ratings, nreviews):
    page_number = 1
    num_reviews_fetched = 0

    while True:
        url2 = url + f'&page={page_number}'
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
            page = requests.get(url2, headers=headers)
            page_html = BeautifulSoup(page.content, "html.parser")
        except Exception as e:
            app.logger.error(f"An error occurred while fetching the URL: {str(e)}")
            return 0

        reviews = page_html.find_all('div', {'class': '_1AtVbE'})
        commentheads_ = page_html.find_all('p', {'class': '_2-N8zT'})
        customernames_ = page_html.find_all('p', {'class': '_2sc7ZR'})
        ratings_ = page_html.find_all('div', {'class': '_3LWZlK'})

        if not reviews:
            break

        for review in reviews:
            x = review.get_text()
            org_reviews.append(re.sub(r'READ MORE', '', x))
            clean_reviews.append(clean_review(x))

        customernames.extend('~' + cn.get_text() for cn in customernames_)
        commentheads.extend(ch.get_text() for ch in commentheads_)

        ra = [int(r.get_text()) if r.get_text().isdigit() and 1 <= int(r.get_text()) <= 5 else 0 for r in ratings_]
        ratings.extend(ra)

        num_reviews_fetched += len(reviews)
        if num_reviews_fetched >= nreviews:
            break

        page_number += 1

    return num_reviews_fetched


# Flask Routes
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/results', methods=['GET'])
def result():
    url = request.args.get('url')
    nreviews = int(request.args.get('num', '10'))

    clean_reviews = []
    org_reviews = []
    customernames = []
    commentheads = []
    ratings = []

    print(f"Fetching URL: {url}")

    # Fetching the URL
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        page = requests.get(url, headers=headers)
        page_html = BeautifulSoup(page.content, "html.parser")
    except Exception as e:
        app.logger.error(f"An error occurred while fetching the URL: {str(e)}")
        return render_template('error.html', message="Error fetching the URL. Please check the URL and try again.")

    proname_elements = page_html.find_all('span', {'class': 'B_NuCI'})
    price_elements = page_html.find_all('div', {'class': '_30jeq3 _16Jk6d'})

    proname = proname_elements[0].get_text() if proname_elements else "Product Name Not Found"
    price = price_elements[0].get_text() if price_elements else "Price Not Found"

    # Getting the link of see all reviews button
    all_reviews_url = page_html.find_all('div', {'class': 'col JOpGWq'})
    if all_reviews_url:
        all_reviews_url = all_reviews_url[0].find_all('a')[-1]
        all_reviews_url = 'https://www.flipkart.com' + all_reviews_url.get('href')
        url2 = all_reviews_url + '&page=1'
    else:
        return render_template('error.html', message="Error extracting reviews link. Please try again.")

    print(f"Fetching reviews from: {url2}")

    num_reviews = 0
    start_time_fetching = time.time()

    # Multithreading implementation for faster processing
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_page_number = {
            executor.submit(extract_all_reviews, url2, clean_reviews, org_reviews, customernames, commentheads, ratings,
                            nreviews): page_number for page_number in range(1, 6)}
        for future in concurrent.futures.as_completed(future_to_page_number):
            num_reviews_iter = future.result()
            num_reviews += num_reviews_iter
            if num_reviews_iter > 0:
                print(f"Fetched {num_reviews_iter} reviews. Total: {num_reviews}")
            if num_reviews >= nreviews:
                break

    end_time_fetching = time.time()
    time_taken_fetching = end_time_fetching - start_time_fetching
    print(f"Time taken to fetch reviews: {time_taken_fetching:.2f} seconds")

    org_reviews = org_reviews[:num_reviews]
    clean_reviews = clean_reviews[:num_reviews]
    customernames = customernames[:num_reviews]
    commentheads = commentheads[:num_reviews]
    ratings = ratings[:num_reviews]

    start_time_wordcloud = time.time()
    for_wc = ' '.join(clean_reviews)
    wcstops = set(STOPWORDS)
    wc = WordCloud(width=1400, height=800, stopwords=wcstops, background_color='white').generate(for_wc)
    plt.figure(figsize=(20, 10), facecolor='k', edgecolor='k')
    plt.imshow(wc, interpolation='bicubic')
    plt.axis('off')
    plt.tight_layout()
    CleanCache(directory='static/images')
    plt.savefig('static/images/woc.png')
    plt.close()
    end_time_wordcloud = time.time()
    time_taken_wordcloud = end_time_wordcloud - start_time_wordcloud
    print(f"Time taken to generate word cloud: {time_taken_wordcloud:.2f} seconds")

    d = [{'review': org_reviews[i], 'cn': customernames[i], 'ch': commentheads[i], 'stars': ratings[i]} for i in range(len(org_reviews))]

    for i in d:
        if i['stars'] != 0:
            i['sent'] = 'NEGATIVE' if i['stars'] in [1, 2] else 'POSITIVE'
        else:
            i['sent'] = 'UNKNOWN'

    np, nn = sum(1 for i in d if i['sent'] == 'POSITIVE'), sum(1 for i in d if i['sent'] == 'NEGATIVE')

    return render_template('result.html', dic=d, n=num_reviews, nn=nn, np=np, proname=proname, price=price)


@app.route('/wc')
def wc():
    return render_template('wc.html')


class CleanCache:
    def __init__(self, directory=None):
        self.clean_path = directory

    def clean(self):
        if os.listdir(self.clean_path) != list():
            files = os.listdir(self.clean_path)
            for fileName in files:
                print(fileName)
                os.remove(os.path.join(self.clean_path, fileName))
        print("Cleaned!")


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=3000, debug=True, threaded=True)
