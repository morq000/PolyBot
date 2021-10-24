from typing import List
import gspread
from oauth2client.service_account import ServiceAccountCredentials


def authorize_drive():
	"""Function to authorize at Google drive"""
	scopes = [
		'https://www.googleapis.com/auth/spreadsheets',
		'https://www.googleapis.com/auth/drive'
	]

	credentials = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scopes)
	client = gspread.authorize(credentials)
	sheet = client.open('test_applications').sheet1
	return sheet

def write_database_to_drive(application_list: List) -> None:
	"""Function to write whole database to google drive"""
	sheet = authorize_drive()
	sheet.insert_rows(application_list)

def add_application_to_drive(application: List) -> None:
	"""This function adds new row with incoming application to the spreadsheet"""
	sheet = authorize_drive()
	last_row = len(sheet.col_values(1))
	sheet.insert_row(values=application, index=last_row+1)