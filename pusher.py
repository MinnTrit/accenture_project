import pandas as pd
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
import gspread
import time

class Pusher:
    def __init__(self, 
                credential_path: str, 
                voucher_spreadsheet: str, 
                product_spreadsheet: str,
                voucher_worksheet: str,
                product_worksheet: str,
                clear_option: bool):
        self.credential_path = credential_path
        self.product_worksheet = self.initialize(product_spreadsheet, product_worksheet)
        self.voucher_worksheet = self.initialize(voucher_spreadsheet, voucher_worksheet)
        self.clear_worksheet(clear_option)
        self.voucher_rows = self.get_current_row_voucher()
        self.product_rows = self.get_current_row_product()
        
    def initialize(self, spreadsheet_name, worksheet_name):
        try: 
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file(self.credential_path, scopes=scope)
            client = gspread.authorize(creds) 
            spreadsheet = client.open(spreadsheet_name) 
            worksheet = spreadsheet.worksheet(worksheet_name)
            print(f'Initialized google client for spreadsheet {spreadsheet_name} worksheet {worksheet}')
            return worksheet
        except gspread.exceptions.SpreadsheetNotFound as e:
            print(f'Spreadsheet {spreadsheet_name} is not found\nError as {e}')
            return None 
        except gspread.exceptions.WorksheetNotFound as e:
            print(f'Worksheet {worksheet_name} of {spreadsheet_name} is not found\nError as {e}')
            return None
    
    def get_current_row_voucher(self):
        existing_data = self.voucher_worksheet.get_all_values()
        last_row = len(existing_data) + 1
        print(f'Retrieved the latest row of the voucher at {last_row}')
        return last_row
    
    def get_current_row_product(self):
        existing_data = self.product_worksheet.get_all_values()
        last_row = len(existing_data) + 1
        print(f'Retrieved the latest row of the product at {last_row}')
        return last_row

    def to_spreadsheet(self, input_list, spreadsheet_type:list[str]=['Product', 'Voucher']):
        input_df = pd.DataFrame(input_list)
        if spreadsheet_type == 'Product':
            pushed_worksheet = self.product_worksheet
            last_row = self.product_rows
            self.product_rows += len(input_df)
        else:
            pushed_worksheet = self.voucher_worksheet
            last_row = self.voucher_rows
            self.voucher_rows += len(input_df)
        while True:
            try: 
                set_with_dataframe(pushed_worksheet, input_df, row=last_row, include_index=False, include_column_header=False)
                break
            except Exception as e:
                print(f"Error occured as {e},\n Sleeping for 5 seconds and retrying")
                time.sleep(10)
                continue

    def clear_worksheet(self, clear_option):
        if clear_option is True:
            self.product_worksheet.batch_clear(['2:1000000'])
            self.voucher_worksheet.batch_clear(['2:1000000'])
            print(f'Cleared the voucher and product spreadsheet')