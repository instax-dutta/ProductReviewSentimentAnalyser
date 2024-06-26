---

# Product Review Sentiments Analyzer

![](https://i.imgur.com/9vhkyEV.png)

## Overview

Product Review Sentiments Analyzer is a web application that fetches and analyzes product reviews from Flipkart, providing insights into customer sentiments. It uses Flask for the backend, BeautifulSoup for web scraping, and includes features like fetching reviews, sentiment analysis, and generating word clouds.

## Features

- **Review Fetching:** Fetches top reviews of a product from Flipkart.
- **Sentiment Analysis:** Analyzes reviews to determine positive and negative sentiments.
- **Word Cloud Generator:** Creates a word cloud from the cleaned reviews for visual representation.

## Technologies Used

- Python
- Flask
- BeautifulSoup
- Requests
- WordCloud

## Setup and Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/instax-dutta/ProductReviewSentimentAnalyser.git
    ```

2. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Run the Flask application:

    ```bash
    python app.py
    ```

4. Open the application in your web browser at [http://127.0.0.1:3000/]().

## Usage

1. Enter the Flipkart product URL and the number of reviews you want to analyze.
2. Click the "Submit" button.
3. Explore the sentiment analysis results, including positive and negative review counts.
4. Navigate to the Word Cloud page for a visual representation of the reviews.



## Contributors

- [Sai Dutta Abhishek Dash](https://github.com/instax-dutta)
- [Jatin Kumar Pradhan](https://github.com/JatinKumarPradhan)
- [Jyotirmayi Sadangi](https://github.com/JyotirmayiSadangi)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [Flask](https://flask.palletsprojects.com/)
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
- [WordCloud](https://github.com/amueller/word_cloud)

Feel free to contribute to the project, report issues, or suggest improvements!

---
