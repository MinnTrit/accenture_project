from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event
import pandas as pd
import requests
import re
import time
import io
import os
import json
import pytz
import calendar

class Processor:
    RETRIES=10
    current_time = datetime.now().strftime('%d%b%H%M')
    def __init__(self,
                 jobs_details:dict, 
                 datalake_client,
                 google_client):
        self.country_list = jobs_details.get('country_list')
        self.clean_cookies_list = self.get_clean_cookies(jobs_details.get('cookies_list'))
        self.domain_map = self.get_domain()
        self.gmt_map = self.get_gmt()
        self.folder_name = os.path.join('uploads', Processor.current_time)
        self.datalake_client = datalake_client
        self.google_client = google_client

    def get_information(self):
        return {
            'country_list': self.country_list, 
            'clean_cookies': self.clean_cookies
        }
    
    def get_domain(self):
        domain_map = {
        "VN": "https://sellercenter.lazada.vn", 
        "ID": "https://sellercenter.lazada.co.id",
        "SG": "https://sellercenter.lazada.sg",
        "MY": "https://sellercenter.lazada.com.my",
        "PH": "https://sellercenter.lazada.com.ph",
        "TH": "https://sellercenter.lazada.co.th"
        }
        return domain_map
    
    def get_gmt(self):
        gmt_map = {
            "VN": pytz.timezone("Asia/Ho_Chi_Minh"), #GMT+7
            "TH": pytz.timezone("Asia/Ho_Chi_Minh"), #GMT+7
            "ID": pytz.timezone("Asia/Ho_Chi_Minh"), #GMT+7
            "MY": pytz.timezone("Asia/Kuala_Lumpur"), #GMT+8
            "PH": pytz.timezone("Asia/Kuala_Lumpur"), #GMT+8
            "SG": pytz.timezone("Asia/Kuala_Lumpur") #GMT+8
        }
        return gmt_map
    
    def get_clean_cookies(self, raw_cookies):
        result_list = []
        for cookies in raw_cookies:
            result_dict = {}
            cookies_df = pd.read_csv(io.StringIO(cookies),sep=";")
            cookies_list = cookies_df.columns.tolist()
            clean_list = [cookie.strip() for cookie in cookies_list]
            for node in clean_list:
                key = node.split("=")[0]
                value = node.split("=")[1]
                result_dict[key] = value
            result_list.append(result_dict)
        return result_list
    
    def get_voucher(self, input_cookies, country_list):
        # print(f'Start getting the voucher, list countries are {country_list}')
        current_directory = os.getcwd()
        voucher_path = os.path.join(current_directory, self.folder_name)
        voucher_directory = os.path.join(voucher_path, 'Voucher Analysis')
        if not os.path.exists(voucher_directory):
            os.makedirs(voucher_directory)
            print(f'Folder path {voucher_directory} created')
        info_path = os.path.join(self.folder_name, 'info.txt')
        master_list = []
        for country in country_list:
            print(f'Processing country {country}')
            domain_url = self.domain_map.get(country, "")
            country_gmt = self.gmt_map.get(country, "")
            seller_url = f'{domain_url}/ba/sycm/faas/dataWar/seller/info.json'
            matching_pattern = r'\w+\.\w+(?:\.co|\.com)?\.(\w+).*'
            seller_response = requests.request("POST", seller_url, cookies=input_cookies)
            seller_id = seller_response.json().get('data')[0].get('sellerId')
            current_country = re.search(matching_pattern, seller_url).group(1).upper()
            seller_used_id = f'{current_country}.LAZ.{seller_id}'
            print(f'Retrieved seller used id at {seller_used_id}')
            result_list = []
            exit_page_loop = False
            for page in range(1, 10):
                if exit_page_loop is True:
                    break
                current_retry = 0
                current_date_range = datetime.now().strftime('%Y-%m-%d')
                while current_retry < Processor.RETRIES:
                    try:
                        request_string = f'{domain_url}/ba/sycm/lazada/promotion/realtime/collectable/performance/list.json?dateType=today&dateRange={current_date_range}|{current_date_range}&pageSize=1000&status=All&page={page}&order=desc&orderBy=voucherStartDate&searchStr='
                        response = requests.request("POST", request_string, cookies=input_cookies)
                        print(f'Made request to {request_string} for seller {seller_used_id}')
                        return_data = response.json()
                        voucher_items = return_data.get('data', '').get('data').get('data')
                        collected_datetime_obj = datetime.now(country_gmt)
                        time_collected = collected_datetime_obj.strftime('%Y-%m-%d %H:%M:%S')
                        if len(voucher_items) > 0:
                            for voucher_item in voucher_items:
                                #Get the voucher name
                                voucher_name = voucher_item.get('voucherName').get('value')
                            
                                #Get the voucher status
                                try: 
                                    voucher_status = voucher_item.get('voucherStatus').get('value')
                                except Exception:
                                    voucher_status = ""

                                #Get the voucher id
                                voucher_id = voucher_item.get('voucherId').get('value')

                                datetime_format = '%Y-%m-%d'
                                #Get the start date string
                                start_date = voucher_item.get('voucherStartDate').get('value')
                                start_timestamp = start_date / 1000
                                start_obj = datetime.fromtimestamp(start_timestamp)
                                startdate_string = start_obj.strftime(datetime_format)

                                #Get the end date string
                                end_date = voucher_item.get('voucherEndDate').get('value')
                                end_timestamp = end_date / 1000
                                end_obj = datetime.fromtimestamp(end_timestamp)
                                enddate_string = end_obj.strftime(datetime_format)

                                valid_period_string = startdate_string + ' - ' + enddate_string

                                #Get the voucher issued
                                voucher_issued = voucher_item.get('issuedVoucherCntStd').get('value')

                                #Get the voucher collected
                                voucher_collected = voucher_item.get('collectedVoucherCountStd').get('value')

                                #Get the voucher redeemed
                                voucher_redeemed = voucher_item.get('redeemedVoucherCountStd').get('value')

                                #Get the collected rate
                                voucher_collect_rate = voucher_item.get('collectedRateStd').get('value')

                                #Get the redeem rate
                                voucher_redeemed_rate = voucher_item.get('redeemedRate').get('value')

                                #Get the roi metric
                                voucher_roi = voucher_item.get('roiStd').get('value')

                                #Get the buyer count metric
                                buyer_count = voucher_item.get('voucherPayOrdBuyerCountStd').get('value')

                                #Get the gmv
                                gmv = voucher_item.get('voucherPayMordAmountStd').get('value')

                                #Get the discount
                                discount = voucher_item.get('discountAmountStd').get('value')

                                #Get the aov
                                aov = voucher_item.get('voucherAvgOrderShare').get('value')

                                json_node = {
                                    'time_collected': time_collected,
                                    'seller_used_id': seller_used_id,
                                    'voucher_name': voucher_name,
                                    'voucher_id': voucher_id,
                                    'voucher_status': voucher_status,
                                    'valid_period': valid_period_string,
                                    'voucher_issued': voucher_issued,
                                    'voucher_collected': voucher_collected,
                                    'voucher_redeemed': voucher_redeemed,
                                    'voucher_collect_rate': voucher_collect_rate,
                                    'voucher_redeemed_rate': voucher_redeemed_rate, 
                                    'redeem_revenue': gmv,
                                    'discount_cost': discount, 
                                    'buyer_count': buyer_count, 
                                    'ROI': voucher_roi,
                                    'AOV': aov, 
                                }
                                result_list.append(json_node)
                                current_retry += Processor.RETRIES
                        elif len(voucher_items) == 0:
                            voucher_path = self.convert_to_json_voucher(result_list, voucher_directory, seller_used_id)
                            self.datalake_client.to_datalake(voucher_path)
                            master_list.extend(result_list[:200])
                            print(f'Country {country}, seller {seller_used_id} appended to voucher master list')
                            if os.path.exists(info_path):
                                write_option = 'a'
                            else:
                                write_option = 'w'
                            with open(info_path, write_option) as file:
                                file.write(f'{seller_used_id}-voucher-{time_collected}\n')
                            exit_page_loop = True
                            break
                    except Exception as e:
                        print(f'Error occured getting the voucher for country {country} as {e}, retrying ...')
                        time.sleep(2)
                        current_retry += 1
        self.google_client.to_spreadsheet(master_list, "Voucher")

    def get_product(self, input_cookies, country_list):
        # print(f'Start getting the products, list countries are {country_list}')
        master_list = []
        current_directory = os.getcwd()
        product_path = os.path.join(current_directory, self.folder_name)
        product_directory = os.path.join(product_path, 'Product Analysis')
        if not os.path.exists(product_directory):
            os.makedirs(product_directory)
            print(f'Folder path {product_directory} created')
        info_path = os.path.join(self.folder_name, 'info.txt')
        for country in country_list:
            current_retry = 0
            while current_retry < Processor.RETRIES:
                try:
                    domain_url = self.domain_map.get(country, "")
                    country_gmt = self.gmt_map.get(country, "")
                    print(f'Processing country {country}')
                    result_list = []
                    product_url = f'{domain_url}/ba/sycm/lazada/faas/product/rank/realtime/itemV2?page=1&pageSize=100&order=desc&orderBy=realtimeProductIpvUv&device=1&indexCode=realtimeProductIpvUv&dashboard=false'
                    response = requests.request("GET", product_url, cookies=input_cookies)
                    print(f"Made request to url {product_url} for country {country}")
                    product_json = response.json()
                    seller_id = product_json.get('data').get('data')[0].get('sellerId').get('value')
                    country = product_json.get('data').get('data')[0].get('venture').get('value')
                    seller_used_id = '.'.join([str(country),str("LAZ"), str(seller_id)])
                    product_path = self.convert_to_json_product(product_json, product_directory, seller_used_id)
                    self.datalake_client.to_datalake(product_path)
                    collected_datetime_obj = datetime.now(country_gmt)
                    time_collected = collected_datetime_obj.strftime('%Y-%m-%d %H:%M:%S')
                    for data in product_json.get('data').get('data'):
                        #Get the dimensions
                        spu_marketplace = data.get('itemId').get('value')
                        spu_used_id = '.'.join([str(country),str("LAZ"), str(seller_id), str(spu_marketplace)])

                        #Get the metrics
                        unique_visitor = data.get('realtimeProductIpvUv').get('value')
                        product_pageview = data.get('realtimeProductIpv').get('value')
                        product_revenue = data.get('realtimeProductRevenue').get('value')
                        product_units_sold = data.get('realtimeProductUnitsSold').get('value')
                        product_orders = data.get('realtimeProductOrders').get('value')
                        add_to_cart_user = data.get('realtimeProductCartByrCnt').get('value')
                        add_unit = data.get('realtimeProductCartItmQty').get('value')
                        add_to_wishlist_user = data.get('realtimeProductWishlistUv').get('value')
                        add_to_wishlist = data.get('realtimeProductWishlistCnt').get('value')
                        customer = data.get('realtimeProductBuyers').get('value')
                        final_node = {
                            'time_collect': time_collected,
                            'seller_id': seller_used_id,
                            'spu':spu_used_id,
                            'page_view': product_pageview,
                            'product_revenue': product_revenue,
                            'product_units_sold': product_units_sold,
                            'product_orders': product_orders,
                            'unique_visitor': unique_visitor,
                            'add_to_cart_user': add_to_cart_user,
                            'add_unit': add_unit,
                            'add_to_wishlist': add_to_wishlist,
                            'add_to_wishlist_user': add_to_wishlist_user,
                            'customer': customer
                        }
                        result_list.append(final_node)
                    master_list.extend(result_list)
                    print(f'Country {country}, seller used id {seller_used_id} appended to product master list')
                    if os.path.exists(info_path):
                        write_option = 'a'
                    else:
                        write_option = 'w'
                    with open(info_path, write_option) as file:
                        file.write(f'{seller_used_id}-product-{time_collected}\n')
                        current_retry += Processor.RETRIES
                except Exception as e:
                    print(f'Error occured getting the product for country {country} as {e}, retrying ...')
                    time.sleep(2)
                    current_retry += 1
        self.google_client.to_spreadsheet(master_list, "Product")

    def convert_to_json_voucher(self, input_json, file_path, seller_used_id):
        reporting_day = datetime.now().strftime("%Y-%m-%d")
        time_downloaded = datetime.now().strftime("%d%b%H%M").lower()     
        file_name = f"{seller_used_id}_{reporting_day}_voucher-realtime-report_{time_downloaded}_auto.json"
        result_path = os.path.join(file_path, file_name)   
        with open(result_path, 'w', encoding='utf-8') as json_file:
            json.dump(input_json, json_file, ensure_ascii=False, indent=4)
        print(f"JSON voucher saved to file: {result_path}") 
        return result_path

    def convert_to_json_product(self, input_json, file_path, seller_used_id):
        reporting_day = datetime.now().strftime("%Y-%m-%d")
        time_downloaded = datetime.now().strftime("%d%b%H%M").lower()    
        file_name = f"{seller_used_id}_{reporting_day}_daily-traffic-realtime-report_{time_downloaded}_auto.json"
        result_path = os.path.join(file_path, file_name)
        with open(result_path, 'w', encoding='utf-8') as json_file:
            json.dump(input_json, json_file, ensure_ascii=False, indent=4)
        print(f"JSON product saved to file: {result_path}") 
        return result_path
    
    def convert_to_json_voucher_yesterday(self, input_json, file_path, seller_used_id):
        yesterday_reporting_day = datetime.now() - timedelta(days=1)
        reporting_day = yesterday_reporting_day.strftime("%Y-%m-%d")
        time_downloaded = datetime.now().strftime("%d%b%H%M").lower()     
        file_name = f"{seller_used_id}_{reporting_day}_voucher-realtime-report_{time_downloaded}_auto.json"
        result_path = os.path.join(file_path, file_name)   
        with open(result_path, 'w', encoding='utf-8') as json_file:
            json.dump(input_json, json_file, ensure_ascii=False, indent=4)
        print(f"JSON voucher saved to file: {result_path}") 
        return result_path
    
    def convert_to_json_product_yesterday(self, input_json, file_path, seller_used_id):
        yesterday_reporting_day = datetime.now() - timedelta(days=1)
        reporting_day = yesterday_reporting_day.strftime("%Y-%m-%d")
        time_downloaded = datetime.now().strftime("%d%b%H%M").lower()    
        file_name = f"{seller_used_id}_{reporting_day}_daily-traffic-realtime-report_{time_downloaded}_auto.json"
        result_path = os.path.join(file_path, file_name)
        with open(result_path, 'w', encoding='utf-8') as json_file:
            json.dump(input_json, json_file, ensure_ascii=False, indent=4)
        print(f"JSON product saved to file: {result_path}") 
        return result_path
    
    def get_yesterday_voucher(self, input_cookies, input_country_list, date_range):
        final_df = pd.DataFrame()
        info_path = os.path.join(self.folder_name, 'info.txt')
        print(f'Current voucher list {input_country_list}')
        for country in input_country_list:
            print(f'Processing voucher for country {country}')
            domain_url = self.domain_map.get(country, "")
            country_gmt = self.gmt_map.get(country, "")
            seller_url = f'{domain_url}/ba/sycm/faas/dataWar/seller/info.json'
            matching_pattern = r'\w+\.\w+(?:\.co|\.com)?\.(\w+).*'
            seller_response = requests.request("POST", seller_url, cookies=input_cookies)
            seller_id = seller_response.json().get('data')[0].get('sellerId')
            current_country = re.search(matching_pattern, seller_url).group(1).upper()
            seller_used_id = f'{current_country}.LAZ.{seller_id}'
            print(f'Retrieved seller used id at {seller_used_id}')
            result_list = []
            exit_page_loop = False
            for page in range(1, 10):
                if exit_page_loop is True:
                    break
                current_retry = 0
                yesterday_object = datetime.now() - timedelta(days=1)
                yesterday_string = yesterday_object.strftime('%Y-%m-%d')
                while current_retry < Processor.RETRIES:
                    try:
                        request_string = f'{domain_url}/ba/sycm/lazada/promotion/realtime/collectable/performance/list.json?dateType=today&date_range={date_range}&pageSize=1000&status=All&page={page}&order=desc&orderBy=voucherStartDate&searchStr='
                        response = requests.request("POST", request_string, cookies=input_cookies)
                        print(f'Made request to {request_string} for seller {seller_used_id}')
                        return_data = response.json()
                        voucher_items = return_data.get('data', '').get('data').get('data')
                        collected_datetime_obj = datetime.now(country_gmt)
                        time_collected = collected_datetime_obj.strftime('%Y-%m-%d %H:%M:%S')
                        if len(voucher_items) > 0:
                            for voucher_item in voucher_items:
                                #Get the voucher name
                                voucher_name = voucher_item.get('voucherName').get('value')

                                #Get the voucher status
                                voucher_status = voucher_item.get('voucherStatus').get('value')

                                #Get the voucher id
                                voucher_id = voucher_item.get('voucherId').get('value')

                                datetime_format = '%Y-%m-%d'
                                #Get the start date string
                                start_date = voucher_item.get('voucherStartDate').get('value')
                                start_timestamp = start_date / 1000
                                start_obj = datetime.fromtimestamp(start_timestamp)
                                startdate_string = start_obj.strftime(datetime_format)

                                #Get the end date string
                                end_date = voucher_item.get('voucherEndDate').get('value')
                                end_timestamp = end_date / 1000
                                end_obj = datetime.fromtimestamp(end_timestamp)
                                enddate_string = end_obj.strftime(datetime_format)

                                valid_period_string = startdate_string + ' - ' + enddate_string

                                #Get the voucher issued
                                voucher_issued = voucher_item.get('issuedVoucherCntStd').get('value')

                                #Get the voucher collected
                                voucher_collected = voucher_item.get('collectedVoucherCountStd').get('value')

                                #Get the voucher redeemed
                                voucher_redeemed = voucher_item.get('redeemedVoucherCountStd').get('value')

                                #Get the collected rate
                                voucher_collect_rate = voucher_item.get('collectedRateStd').get('value')

                                #Get the redeem rate
                                voucher_redeemed_rate = voucher_item.get('redeemedRate').get('value')

                                #Get the roi metric
                                voucher_roi = voucher_item.get('roiStd').get('value')

                                #Get the buyer count metric
                                buyer_count = voucher_item.get('voucherPayOrdBuyerCountStd').get('value')

                                #Get the gmv
                                gmv = voucher_item.get('voucherPayMordAmountStd').get('value')

                                #Get the discount
                                discount = voucher_item.get('discountAmountStd').get('value')

                                #Get the aov
                                aov = voucher_item.get('voucherAvgOrderShare').get('value')

                                json_node = {
                                    'time_collected': time_collected,
                                    'day': yesterday_string,
                                    'seller_used_id': seller_used_id,
                                    'voucher_name': voucher_name,
                                    'voucher_id': voucher_id,
                                    'voucher_status': voucher_status,
                                    'valid_period': valid_period_string,
                                    'voucher_issued': voucher_issued,
                                    'voucher_collected': voucher_collected,
                                    'voucher_redeemed': voucher_redeemed,
                                    'voucher_collect_rate': voucher_collect_rate,
                                    'voucher_redeemed_rate': voucher_redeemed_rate, 
                                    'redeem_revenue': gmv,
                                    'discount_cost': discount, 
                                    'buyer_count': buyer_count, 
                                    'ROI': voucher_roi,
                                    'AOV': aov, 
                                }
                                result_list.append(json_node)
                                current_retry += Processor.RETRIES
                        elif len(voucher_items) == 0:
                            voucher_df = pd.DataFrame(result_list[:200])
                            final_df = pd.concat([final_df, voucher_df], ignore_index=True)
                            destinated_path = os.path.join(self.folder_name, "Yesterday")
                            destinated_voucher_path = os.path.join(destinated_path, "Voucher Analysis")
                            if not os.path.exists(destinated_voucher_path):
                                os.makedirs(destinated_voucher_path)
                            self.convert_to_json_voucher_yesterday(result_list, destinated_voucher_path, seller_used_id)
                            if os.path.exists(info_path):
                                write_option = 'a'
                            else:
                                write_option = 'w'
                            with open(info_path, write_option) as file:
                                file.write(f'{seller_used_id}-voucher-{time_collected}\n')
                            exit_page_loop = True
                            break
                    except Exception:
                        print(f'Error occured getting the voucher for country {country}, retrying ...')
                        time.sleep(2)
                        current_retry += 1
        self.google_client.to_spreadsheet(result_list, "Voucher")

    def get_yesterday_product(self, input_cookies, input_country_list, date_range):
        first_date_parameter = date_range.split('|')[0]
        last_date_parameter = date_range.split('|')[1]
        if first_date_parameter == last_date_parameter:
            datetype = 'day'
        else:
            datetype = 'month'
        final_df = pd.DataFrame()
        print(f'Current product country list {input_country_list}')
        for country in input_country_list:
            domain_url = self.domain_map.get(country, "")
            country_gmt = self.gmt_map.get(country, "")
            collected_datetime_obj = datetime.now(country_gmt)
            time_collected = collected_datetime_obj.strftime('%Y-%m-%d %H:%M:%S')
            product_url = f'{domain_url}/ba/sycm/lazada/faas/product/rank/realtime/itemV2?page=1&pageSize=1&order=desc&orderBy=realtimeProductIpvUv&device=1&indexCode=realtimeProductIpvUv&dashboard=false'
            response = requests.request("GET", product_url, cookies=input_cookies)
            product_json = response.json()
            seller_id = product_json.get('data').get('data')[0].get('sellerId').get('value')
            country = product_json.get('data').get('data')[0].get('venture').get('value')
            seller_used_id = '.'.join([str(country),str("LAZ"), str(seller_id)])
            print(f'Retrieved seller {seller_used_id} for country {country}')
            info_path = os.path.join(self.folder_name, 'info.txt')
            yesterday_datetime = datetime.now() - timedelta(days=1)
            yesterday_datetime_string = yesterday_datetime.strftime('%Y-%m-%d')
            yesterday_product_url = f"{domain_url}/ba/sycm/lazada/faas/product/performance/batch/itemV2.json?dateRange={date_range}&dateType={datetype}&page=1&pageSize=1000&orderBy=productRevenue&order=desc"
            current_retry = 0
            while current_retry < Processor.RETRIES:
                try:
                    response = requests.request('POST', yesterday_product_url, cookies=input_cookies)
                    raw_data = response.json().get('data').get('data')
                    result_list = []
                    current_datetime_object = datetime.now()
                    for data_point in raw_data:
                        spu_id_marketplace = data_point.get('itemId').get('value')
                        product_name = data_point.get('productName').get('value')
                        product_url = data_point.get('link').get('value')
                        sku_id_list = data_point.get('skuIdList').get('value')
                        product_visitor = data_point.get('productIpvUv').get('value')
                        product_pageview = data_point.get('productIpv').get('value')
                        product_visitor_value = data_point.get('productVisitorValue').get('value')
                        product_add_to_cart_units = data_point.get('productCartItmQty').get('value')
                        product_add_to_cart_users = data_point.get('productCartByrCnt').get('value')
                        product_add_to_cart_conversion = data_point.get('productAddToCartConversionRate').get('value')
                        product_wishlist_user = data_point.get('productWishlistUv').get('value')
                        product_wishlist = data_point.get('productWishlistCnt').get('value')
                        product_buyers = data_point.get('productBuyers').get('value')
                        product_orders = data_point.get('productOrders').get('value')
                        product_units_sold = data_point.get('productUnitsSold').get('value')
                        product_revenue = data_point.get('productRevenue').get('value')
                        product_conversion_rate = data_point.get('productConversionRate').get('value')
                        product_revenue_per_buyer = data_point.get('productRevenuePerBuyer').get('value')
                        product_revenue_share = data_point.get('productRevenueShare').get('value')
                        spu_json_data = {
                            'time_collected': time_collected,
                            'day': yesterday_datetime_string,
                            'seller_used_id': seller_used_id,
                            'Product ID': spu_id_marketplace,
                            'Product Name': product_name,
                            'URL': product_url,
                            'Seller SKU': '-',
                            'SKU ID': '-',
                            'Product Visitors': product_visitor,
                            'Product Pageviews': product_pageview,
                            'Visitor Value': round(product_visitor_value, 2),
                            'Add to Cart Users': product_add_to_cart_users,
                            'Add to Cart Units': product_add_to_cart_units,
                            'Add to Cart Conversion Rate': product_add_to_cart_conversion,
                            'Wishlist Users': product_wishlist_user,
                            'Wishlist': product_wishlist,
                            'Buyers': product_buyers,
                            'Orders': product_orders,
                            'Units Sold': product_units_sold,
                            'Revenue': product_revenue,
                            'Conversion Rate': product_conversion_rate,
                            'Revenue per Buyer': product_revenue_per_buyer,
                            'Revenue Share': product_revenue_share
                            }
                        result_list.append(spu_json_data)
                        for sku_id_marketplace in sku_id_list:
                            sku_json_data = {
                            'time_collected': time_collected,
                            'day': yesterday_datetime_string,
                            'seller_used_id': seller_used_id,
                            'Product ID': spu_id_marketplace,
                            'Product Name': product_name,
                            'URL': f'{product_url}-i{spu_id_marketplace}-s{sku_id_marketplace}.html?urlFlag=true',
                            'Seller SKU': '-',
                            'SKU ID': sku_id_marketplace,
                            'Product Visitors': '-',
                            'Product Pageviews': '-',
                            'Visitor Value': '-',
                            'Add to Cart Users': product_add_to_cart_users,
                            'Add to Cart Units': product_add_to_cart_units,
                            'Add to Cart Conversion Rate': '-',
                            'Wishlist Users': product_wishlist_user,
                            'Wishlist': product_wishlist,
                            'Buyers': product_buyers,
                            'Orders': product_orders,
                            'Units Sold': product_units_sold,
                            'Revenue': product_revenue,
                            'Conversion Rate': '-',
                            'Revenue per Buyer': product_revenue_per_buyer,
                            'Revenue Share': product_revenue_share
                            }
                            result_list.append(sku_json_data)
                    df = pd.DataFrame(result_list)
                    current_datetime_string = current_datetime_object.strftime('%Y-%m-%d')
                    file_name = f'{seller_used_id}_{yesterday_datetime_string}_traffic-report_{current_datetime_string}_auto_daily.xlsx'
                    destinated_path = os.path.join(self.folder_name, "Yesterday")
                    destinated_product_path = os.path.join(destinated_path, "Product Analysis")
                    if not os.path.exists(destinated_product_path):
                        os.makedirs(destinated_product_path)
                    self.convert_to_json_product_yesterday(result_list, destinated_product_path, seller_used_id)
                    final_df = pd.concat([final_df, df], ignore_index=True)
                    if os.path.exists(info_path):
                        write_option = 'a'
                    else:
                        write_option = 'w'
                    with open(info_path, write_option) as file:
                        file.write(f'File {file_name} saved for seller {seller_used_id}')
                    break
                except Exception as e:
                    print(f'Error occured getting the json data for seller {seller_used_id} as {e}, retrying ...')
                    time.sleep(2)
                    current_retry += 1
        self.google_client.to_spreadsheet(result_list, "Product")

    def generate_date_range(self, reports_type):
        today = datetime.today()
        
        if reports_type == "FullDay":
            yesterday = today - timedelta(days=1)
            return f"{yesterday.strftime('%Y-%m-%d')}|{yesterday.strftime('%Y-%m-%d')}"
        
        elif reports_type == "Monthly":
            first_day_of_prev_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            last_day_of_prev_month = first_day_of_prev_month.replace(
                day=calendar.monthrange(first_day_of_prev_month.year, first_day_of_prev_month.month)[1]
            )
            return f"{first_day_of_prev_month.strftime('%Y-%m-%d')}|{last_day_of_prev_month.strftime('%Y-%m-%d')}"

    def get_all_data(self, reports_type):
        if len(self.clean_cookies_list) != len(self.country_list):
            raise ValueError("Cookies list and country list must have the same length")
        with ThreadPoolExecutor(max_workers=len(self.clean_cookies_list)*len(self.country_list)) as executor:
            for index in range(len(self.clean_cookies_list)):
                input_cookies = self.clean_cookies_list[index]
                input_country_list = self.country_list[index]
                if reports_type == 'Realtime':
                    executor.submit(self.get_product, input_cookies, input_country_list)
                    executor.submit(self.get_voucher, input_cookies, input_country_list)
                else: 
                    date_range = self.generate_date_range(reports_type)
                    executor.submit(self.get_yesterday_product, input_cookies, input_country_list, date_range)
                    executor.submit(self.get_yesterday_voucher, input_cookies, input_country_list, date_range)
    
