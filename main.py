from urllib.request import urlopen
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import datetime
import telegram


goldenCrossStockList = []


telegramToken = '각자의 텔레그램 토큰을 입력해주세요.'
bot = telegram.Bot(token=telegramToken)

kosdaq200_list_dic = {}

stock_list = []

def get_stock_from_txt():
    file = open('stock_list.txt', 'r')
    while (1):
        line = file.readline()
        try:
            escape = line.index('\n')
        except:
            escape = len(line)

        if line:
            stock_list.append(line[0:escape])
        else:
            break
    file.close
    file = open('recommend_list.txt', 'r')
    while (1):
        line = file.readline()
        try:
            escape = line.index('\n')
        except:
            escape = len(line)

        if line:
            stock_list.append(line[0:escape])
        else:
            break
    file.close


def run():
    print('급등주 알리미 시작합니다.')
    isStockSend = {}
    isGetStock = False
    is_ready = False

    while True:
        now = datetime.datetime.now()
        open_market = now.replace(hour=9, minute=10, second=0, microsecond=0)
        close_market = now.replace(hour=15, minute=30, second=0, microsecond=0)
        get_stock_time = now.replace(hour=16, minute=00, second=0, microsecond=0)

        if now >= get_stock_time and not isGetStock:
            open('recommend_list.txt', 'w').close()  # 이전 파일내용 삭제.
            getStockData()
            send_golden_stock()
            isGetStock = True
            is_ready = False

        if now >= open_market and now < close_market:
            if not is_ready:
                get_stock_from_txt()
                for stockCd in stock_list:
                    isStockSend[stockCd] = False

                if isGetStock:
                    isGetStock = False

                is_ready = True

            for stockCd in stock_list:
                try: #국문 URL은 한국거래소에서 종목을 못가져올 때가 있다.
                    stockUrl = 'http://asp1.krx.co.kr/servlet/krx.asp.XMLSiseEng?code='+stockCd
                    reqStock = urlopen(stockUrl)

                    bsObjStock = BeautifulSoup(reqStock, 'lxml-xml')
                    currStockInfo = bsObjStock.find('TBL_StockInfo')
                    prevStockInfo = bsObjStock.find_all('DailyStock')

                    stockName = currStockInfo['JongName']
                    currPrice = float(currStockInfo['CurJuka'].replace(',',''))
                    prevHighPrice = float(prevStockInfo[1]['day_High'].replace(',',''))
                    prevLowPrice = float(prevStockInfo[1]['day_Low'].replace(',',''))
                    startPrice = float(currStockInfo['StartJuka'].replace(',',''))
                    prevRange = (prevHighPrice - prevLowPrice) * 0.5
                    tagetPrice = startPrice + prevRange

                    if currPrice > tagetPrice and not isStockSend[stockCd]:
                        bot.send_message(chat_id='각자의 chat id를 입력해주세요.', text=stockName+'('+stockCd+') : 변동성 돌파! 현재가 : '\
                                                                   + str(currPrice) + '타겟가 : ' + str(tagetPrice))
                        isStockSend[stockCd] = True
                    time.sleep(0.1)
                except:
                    continue
        time.sleep(1)



def getStockData():
    kosdaq200List = []
    for page in range(1, 5):
        kosdaqUrl = 'https://finance.naver.com/sise/sise_market_sum.nhn?sosok=1&page=' + str(page)  # 1페이지당 50종목
        reqKosdaq = urlopen(kosdaqUrl)
        bsObjKosdaq = BeautifulSoup(reqKosdaq, 'html.parser')
        kosdaqList = bsObjKosdaq.find_all('a', {'class': 'tltle'})

        for codeKosdaq in kosdaqList:
            try:
                kosdaqCmpNm = codeKosdaq.get_text()
                kosdaqHrefTxt = codeKosdaq.get('href')
                kosdaqPattern = re.compile(r'\d+')  # \d+ : 숫자가 하나 이상이어야 함
                codeKosdaqTxt = re.search(kosdaqPattern, kosdaqHrefTxt)
                if codeKosdaqTxt != None:
                    kosdaqCd = str(codeKosdaqTxt.group())
                    kosdaq200_list_dic[kosdaqCd] = kosdaqCmpNm
                    kosdaq200List.append(kosdaqCd)
            except:
                continue
        time.sleep(0.1)
    makeDataFrame(kosdaq200List)

def getGoldenCrossStock(df):
    goldenDf = df.sort_values(by=['날짜'], axis=0)  # 날짜를 기준으로 오름차순으로 정렬
    goldenDf.reset_index(drop=True, inplace=True)
    ma60 = goldenDf['종가'].rolling(60).mean()
    ma20 = goldenDf['종가'].rolling(20).mean()  # 단순 20일선 20일평균이기 때문에 처음 19개는 결측값이 생김
    ma5 = goldenDf['종가'].rolling(5).mean()  # 단순 5일선 5일평균이기 때문에 처음 4개는 결측값이 생김
    ma20.dropna(axis=0, inplace=True)
    ma5.dropna(axis=0, inplace=True)
    if ma20.iloc[-1] >= ma20.iloc[-2] >= ma20.iloc[-3]:  # 20일선 우상향 or 횡보
        if ma5.iloc[-1] > ma5.iloc[-2] > ma5.iloc[-3]: # 5일선 우상향
            if ma5.iloc[-2] < ma20.iloc[-2] and ma5.iloc[-1] >= ma20.iloc[-1]: # 5일선이 막 20일선을 돌파
                return True

    if ma20.iloc[-1] > ma20.iloc[-2] > ma20.iloc[-3]: # 20일선 우상향
        if ma20.iloc[-2] < ma60.iloc[-2] and ma20.iloc[-1] >= ma60.iloc[-1]: # 20일선이 막 60일선을 돌파
            return True
        else:
            return False       
    else:
        return False



def makeDataFrame(codeList):
    for code in codeList:
        stockDf = pd.DataFrame()
        for page in range(1, 21): #200일 데이터 가져옴(21) (1페이지당 10거래일 DATA)
            priceUrl = 'https://finance.naver.com/item/sise_day.nhn?code='+str(code)+'&page='+str(page)
            stockDf = stockDf.append(pd.read_html(priceUrl, header=0)[0], ignore_index=True)
            time.sleep(0.1)
        stockDf = stockDf.dropna() #결측값 행 삭제
        if getGoldenCrossStock(stockDf):
            goldenCrossStockList.append(code)
        #if getVolumeStock(stockDf):
        #    volumneStock.append(code)

def send_golden_stock():
    if len(goldenCrossStockList) > 0:
        with open('recommend_list.txt', 'at') as f:
            for goldenItem in goldenCrossStockList:
                f.write(goldenItem)
                f.write("\n")

        recomStockStr = ''
        bot.send_message(chat_id='각자의 chat id를 입력해주세요.', text='추천주가 생성되었습니다.')
        for goldenCd in goldenCrossStockList:
            stockName = getStockName(goldenCd)
            recomStockStr += stockName+'('+goldenCd+')' + ' ,'

        bot.send_message(chat_id='각자의 chat id를 입력해주세요.', text=recomStockStr)
        print("금일의 추천주" + recomStockStr)
    else:
        bot.send_message(chat_id='각자의 chat id를 입력해주세요.', text='금일은 추천주가 없습니다.')
        print("금일은 추천주가 없습니다.")

def getStockName(stockCd):
    url = 'https://finance.naver.com/item/main.nhn?code=' + stockCd
    reqStockName = urlopen(url)
    bsStockName = BeautifulSoup(reqStockName, 'html.parser')
    findList = bsStockName.find_all('dl', {'class': 'blind'})
    for item in findList:
        stockName = item.find('strong')
    return stockName.get_text()

if __name__ == '__main__':
    run()
