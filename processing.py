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

class Processor:
    current_time = datetime.now().strftime('%d%b%H%M')
    def __init__(self,
                 jobs_details:dict, 
                 datalake_client,
                 google_client):
        self.country_list = jobs_details.get('country_list')
        self.clean_cookies_list = self.get_clean_cookies(jobs_details.get('cookies_list'))
        self.domain_map = self.get_domain()
        self.folder_name = fr'uploads\{Processor.current_time}'
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
            domain_url = self.domain_map.get(country)
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
                retries = 5
                current_retry = 0
                current_date_range = datetime.now().strftime('%Y-%m-%d')
                while current_retry < retries:
                    try:
                        request_string = f'{domain_url}/ba/sycm/lazada/promotion/realtime/collectable/performance/list.json?dateType=today&dateRange={current_date_range}|{current_date_range}&pageSize=1000&status=All&page={page}&order=desc&orderBy=voucherStartDate&searchStr='
                        response = requests.request("POST", request_string, cookies=input_cookies)
                        print(f'Made request to {request_string} for seller {seller_used_id}')
                        return_data = response.json()
                        voucher_items = return_data.get('data', '').get('data').get('data')
                        collected_time_stamp_ms = return_data.get('data').get('timestamp')
                        collected_time_stamp_s = collected_time_stamp_ms / 1000
                        collected_datetime_obj = datetime.fromtimestamp(collected_time_stamp_s)
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
                                current_retry += 5
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
            retries = 5
            while current_retry < retries:
                try:
                    domain_url = self.domain_map.get(country, '')
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
                    time_collected = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
                        current_retry += 5
                except Exception as e:
                    print(f'Error occured getting the product for country {country} as {e}, retrying ...')
                    time.sleep(2)
                    current_retry += 1
        self.google_client.to_spreadsheet(master_list, "Product")

    def clear_work_sheet(spreadsheet, clear_voucher_option, worksheet_name):
        if clear_voucher_option is True:
            worksheet = spreadsheet.worksheet(worksheet_name)
            worksheet.batch_clear(['2:1000000'])
            print('Cleared the voucher spreadsheet')

    def convert_to_json_voucher(self, input_json, file_path, seller_used_id):
        reporting_day = datetime.now().strftime("%Y-%m-%d")
        time_downloaded = datetime.now().strftime("%d%b%H%M").lower()     
        file_name = f"{seller_used_id}_{reporting_day}_voucher-realtime-report_{time_downloaded}_auto.json"
        result_path = os.path.join(file_path, file_name)   
        with open(result_path, 'w', encoding='utf-8') as json_file:
            json.dump(input_json, json_file, ensure_ascii=False, indent=4)
        print(f"JSON product saved to file: {result_path}") 
        return result_path

    def convert_to_json_product(self, input_json, file_path, seller_used_id):
        reporting_day = datetime.now().strftime("%Y-%m-%d")
        time_downloaded = datetime.now().strftime("%d%b%H%M").lower()    
        file_name = f"{seller_used_id}_{reporting_day}_daily-traffic-realtime-report_{time_downloaded}_auto.json"
        result_path = os.path.join(file_path, file_name)
        with open(result_path, 'w', encoding='utf-8') as json_file:
            json.dump(input_json, json_file, ensure_ascii=False, indent=4)
        print(f"JSON voucher saved to file: {result_path}") 
        return result_path

    def get_all_data(self):
        if len(self.clean_cookies_list) != len(self.country_list):
            raise ValueError("Cookies list and country list must have the same length")
        with ThreadPoolExecutor(max_workers=len(self.clean_cookies_list)*len(self.country_list)) as executor:
            for index in range(len(self.clean_cookies_list)):
                input_cookies = self.clean_cookies_list[index]
                input_country_list = self.country_list[index]
                executor.submit(self.get_product, input_cookies, input_country_list)
                executor.submit(self.get_voucher, input_cookies, input_country_list)
    
