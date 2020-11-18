import requests
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import time
from time import sleep
import csv

headers = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.193 Safari/537.36'}
base_url = "https://www.amazon.co.uk/"
html_parser = 'html.parser'

def css_select(soup, css_selector):
    """
    Returns the content of the element pointed by the CSS selector, or an empty
    string if not found
    """
    selection = soup.select(css_selector)
    retour = ""
    if len(selection) > 0:
        if hasattr(selection[0], 'text'):
            retour = selection[0].text.strip()
    return retour

def get_search_url(keywords):
    """ Get the search URL, based on the keywords passed """
    search_url = urljoin(base_url, keywords)
    return search_url

def get(url):
    """ GET request with the proper headers """
    ret =  requests.get(url, headers=headers)
    print(f'ret.status_code: ', ret.status_code)
    if ret.status_code != 200:
        print('denied')
        raise ConnectionError(
            'Status code {status} for url {url}\n{content}'.format(
                status=ret.status_code, url=url, content=ret.text))
    return ret.text

def num_cleaner(mystring):
    trim = re.compile(r"[^\d.,]+")
    return trim.sub("", mystring)


def dictwriter_to_csvfile(product_dict_list, file_name, dict_key=""):
    """Write Dictionary List to CSV file"""
    if dict_key:
        fieldnames = dict_key
    else:
        fieldnames = list(product_dict_list[0].keys())
    csvfile = open(file_name, "w", encoding="utf8", newline="")
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(product_dict_list)
    csvfile.close()


def get_last_page(keywords="", search_url=""):
    """Get the last page number from  a search page"""

    if search_url == "":
        search_url = get_search_url(keywords)

    page_html = get(search_url)
    soup = BeautifulSoup(page_html, html_parser)
    print(f'soup.title: ', soup.title)
    css_title_list = [
        "#nav-search-dropdown-card > div > div > span",
        "#searchDropdownBox option[selected]",
    ]

    title_soup = soup.select(css_title_list[1])
    print(f'title_soup: {title_soup}')

    selector_count = 0
    title_name = "amazon.co.uk"
    for selector in css_title_list:
        selector_count += 1
        title_name = css_select(soup, selector)
        print(f'title_name: {title_name}')
        if title_name:
            break

    # get last page
    css_last_page = [
        "li+ .a-disabled",
        ".a-normal~ .a-normal+ .a-normal a",
        ".a-normal+ .a-normal a",
    ]

    for selector in css_last_page:
        last_page = css_select(soup, selector)
        if last_page:
            break

    if not last_page:
        try:
            last_page = soup.find("li", {"class": "a-last"}).previous_sibling
            last_page = last_page.previous_sibling.getText()
        except:
            last_page = 0

    if type(last_page) == str:
        last_page = int(last_page)

    return last_page, title_name


def get_price_outer(product):
    '''Get the price of each product from the product search result'''

    selector_price = ["span[data-a-color=base] .a-offscreen", ]
    for selector in selector_price:
        price_outer = css_select(product, selector)
        try:
            price_outer = float(num_cleaner(price_outer.split(" ")[0]).replace(",", ""))
            break
        except ValueError:
            pass
    if not price_outer:
        return 0

    return price_outer

def get_sellers_name_inner(product):
    """return the inner name of the seller"""
    seller_name = ""
    selles_channel = ""
    if not seller_name:
        merchant_info_selector = "#merchant-info"
        seller_names = css_select(product, merchant_info_selector)
        if "dispatched" in seller_names.lower():
            seller_name = seller_names.split("by")[1].strip().replace(".", "")
            if seller_name == "Amazon":
                selles_channel = "AMZ"
            else:
                selles_channel = "FBM"

        elif "fulfilled" in seller_names.lower():
            seller_name = seller_names.split("and Fulfilled")[0].split("by")[1].strip()
            selles_channel = "FBA"

    return seller_name, selles_channel


def parse_inner_property(search_url):
    """Retrieve the page at search_url"""
    page_html = get(search_url)
    """ Extract the products on a given HTML page of website results """
    soup = BeautifulSoup(page_html, "lxml")

    info_dict = {}
    # get Amazon Bestsellers Rank (BSR) or other product identification
    selector_BSR = [
        "#productDetails_detailBullets_sections1 td > span > span:nth-child(1)"
    ]
    BSR = ''
    for selector in selector_BSR:
        BSR = css_select(soup, selector)
        if BSR:
            seller_rank = BSR.strip().split(" ")[0]
            rank_category = BSR.strip().split("in")[1].split("(")[0].strip()
            break

    if not BSR:
        seller_rank = ""
        rank_category = ""

    offer_new = 0
    selector_offers = [
        ".a-box-inner .olp-text-box",
        "#olp-sl-new-used .a-link-normal span:nth-child(1)",
        "span > a > div > div.olp-text-box"
    ]

    selector_count = 0
    for selector in selector_offers:
        selector_count += 1
        offers_soup = css_select(soup, selector)
        if offers_soup:
            try:
                offer_new = re.search(r"\((\d+)\)", str(offers_soup))
                offer_new = int(offer_new.groups()[0])
                break
            except:
                offer_new = re.search(r"(\d+)", str(offers_soup))
                offer_new = int(offer_new.groups()[0])
                break

    selector_price = "#priceblock_ourprice"
    price = css_select(soup, selector_price)
    if price:
        price = num_cleaner(price)
    else:
        price = ""

    # get price and fulfillment channel
    seller_buybox, seller_channel = get_sellers_name_inner(soup)

    info_dict = {
        'seller_rank': seller_rank,
        'rank_category':rank_category,
        'offer_new': offer_new,
        'price': price,
        'seller_buybox': seller_buybox,
        'seller_channel': seller_channel
    }


    return info_dict


def parse_outer_property(keywords="", search_url=""):
    if search_url == "":
        search_url = get_search_url(keywords)
    part_url = search_url + "&page="

    css_selector = ".s-result-list.s-search-results.sg-row > div.s-result-item.s-asin"

    last_page, title_name = get_last_page(keywords="", search_url=search_url)
    last_page = int(last_page)

    page_number = 1
    all_product = 0

    product_dict_list = []
    while page_number < last_page + 1:
        """Retrieve the page at `search_url`"""
        page_html = get(search_url)
        """
        Extract the products on a given HTML page of Amazon results and return
        the URL of the next page of results
        """
        soup = BeautifulSoup(page_html, "lxml")
        products = soup.select(css_selector)

        count_product = 0
        if len(products) >= 1:
            for product in products:
                # get title
                selector_title = ".a-color-base.a-text-normal"
                selector = selector_title
                title = css_select(product, selector)

                # get the product asin
                asin = product.get("data-asin")

                # get product prices
                price = get_price_outer(product)

                product_dict = {
                    'asin': asin,
                    'price': price,
                    'title': title,
                }
                #
                # -------------------------------------------
                # get product inner properties
                product_url = urljoin(base_url, f"gp/product/{asin}")
                product_dict.update(parse_inner_property(product_url))
                #---------------------------------------------
                #
                # list of all products
                product_dict_list.append(product_dict)
                count_product += 1

        # increase the page number
        page_number += 1
        all_product += count_product
        print('Page_number: ', page_number)

        try:
            _PART_URL = part_url + str(page_number)
            search_url = urljoin(base_url, _PART_URL)
            print("search_url: ", search_url)
        except:
            pass

    return product_dict_list


if __name__ == "__main__":
    search_url = "https://www.amazon.co.uk/s?i=merchant-items&me=A16X0KWD9ZHAAR"  # storefront search
    # search_url = "https://www.amazon.co.uk/s?k=The+Body+Shop&ref=bl_dp_s_web_19851340031"  # Brand or keyword serarch

    last_page, title_name = get_last_page(keywords="", search_url=search_url)
    part_filename = re.sub(r"[^A-Za-z1-9]+", "", title_name)
    print(f'search_url: {search_url}')
    print(f'last_page: {last_page}, title_name: {title_name}, part_filename: {part_filename}')
    product_dict_list = parse_outer_property(keywords="", search_url=search_url)

    print(" ... Finished scraping ...")
    filename = "amazon.co.uk_" + part_filename + ".csv"

    desired_ordered_key = [
        "asin",
        "seller_rank",
        "offer_new",
        "title",
        "rank_category",
        "price",
        "seller_buybox",
        "seller_channel",
    ]

    dictwriter_to_csvfile(product_dict_list, filename, dict_key=desired_ordered_key)
    print(" ... Finished writing to csv file ...")
