from __future__ import print_function
import os.path
import warnings as Warning

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from flask import Flask,request,abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot import LineBotSdkDeprecatedIn30
from datetime import datetime

import os

Warning.filterwarnings("ignore", category=LineBotSdkDeprecatedIn30) # 忽略Line bot 的警告

#line Bot設定


#初始化設定Line Bot API
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 權限範圍，只讀信件即可
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def google_account_info():
    creds = None

    #-----驗證(Start)-----
    # 如果有 token.json，直接載入（避免重複登入授權）
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json",SCOPES)

    # 如果沒有，走 OAuth 流程
    if not creds or not creds.valid:
        # 如token過期 or 需要更新token
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # 把更新後的授權資訊存到token.json
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials = creds)  # 建立 Gmail API client

    return service
    #-----驗證(End)-----

    
def GetGmailMsg(bankTitle):
    service = google_account_info() # 連結驗證google帳號

    match(bankTitle):
        case "中信繳費查詢":
            queryText = 'from:(bank.csc@inib.ctbcbank.com) subject:("繳費交易結果通知") newer_than:30d'
            queryResult = service.users().messages().list(userId="me", q=queryText , maxResults=2).execute().get("messages", []) # 成功搜尋到的信件ID清單

            if queryResult:
                for queryEmailListVal in queryResult:
                    emailID = queryEmailListVal["id"] # 取得信件的ID
                    emailDetail = service.users().messages().get(userId="me", id=emailID).execute() # 分析信件的明細    
                    prefixIndex = emailDetail["snippet"].find("繳費金額") +5
                    suffixIndex = emailDetail["snippet"].find("繳費帳號") -1
                    amount = emailDetail["snippet"][prefixIndex:suffixIndex]

                    #取得繳費時間
                    for emailDetailVal in emailDetail["payload"]["headers"]:
                        if emailDetailVal["name"] == "Date":
                            payDate = emailDetailVal["value"]
                            strptimePayDate = datetime.strptime(payDate, "%a, %d %b %Y %H:%M:%S %z") # 解析原始的格式
                            formattedPayDate = strptimePayDate.strftime("%Y/%m/%d") # 轉成我想要的格式
                resp = "已繳費資訊：" + formattedPayDate + " $" + amount
                return resp
            else :
                return "查無中信繳款紀錄" 
        case "富邦繳費查詢":
            queryText = 'subject:("台北富邦銀行收到您繳納信用卡") newer_than:30d'
            queryResult = service.users().messages().list(userId="me", q=queryText , maxResults=2).execute().get("messages",[]) # 成功搜尋到的信件ID清單

            if queryResult:
                for queryEmailListVal in queryResult:
                    emailID = queryEmailListVal["id"] # 取得信件的ID
                    emailDetail = service.users().messages().get(userId="me", id=emailID).execute() # 分析信件的明細
                    prefixIndex = emailDetail["snippet"].find("說明") + 3
                    suffixIndex = emailDetail["snippet"].find("富邦E化")
                    result = "已繳費資訊：" + emailDetail["snippet"][prefixIndex:suffixIndex]
                    return result
            else:
                return "查無富邦繳款紀錄"
        case _:
            queryText = ""

# -------------------
# Flask + LINE Bot
# 建立輕量級的webapi
# -------------------

app = Flask(__name__)

#Line驗證
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature'] #簽章
    body = request.get_data(as_text=True) #回傳格式
    try:
        handler.handle(body,signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent , message = TextMessage)
def handle_message(event):
    lineText = event.message.text
    
    match(lineText):
        case "中信繳費查詢" :
            result = GetGmailMsg("中信繳費查詢")
        case "富邦繳費查詢" :
            result = GetGmailMsg("富邦繳費查詢")
        case _:
            result = "查無對應銀行"

    line_bot_api.push_message(USER_ID, TextSendMessage(text = result)) #推播到Line

app.run(port = 500)