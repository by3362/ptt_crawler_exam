import requests
from bs4 import BeautifulSoup
import sys
import json
from datetime import datetime
from datetime import timedelta
import pandas

PTT_URL = "https://www.ptt.cc"

def get_web_page(url):
    resp = requests.get(
        url=url,
        cookies={"over18" : "1"}
    )

    if resp.status_code != 200:
        print("Invalid url : ", resp.url)
    else:
        return resp.text

def get_articles(dom, date_list):
    soup = BeautifulSoup(dom, "html5lib")
    
    # 取得上一頁連結
    paging_div = soup.find("div", "btn-group btn-group-paging")
    prev_url = paging_div.find_all("a")[1]["href"]

    articles = [] # 儲存取得的文章資料
    divs = soup.find_all("div", "r-ent")
    for d in divs:
        article_date=d.find("div", "date").text.strip()
        if article_date in date_list: # 發文日期為今日
            # 取得推文數
            push_count = 0
            push_str = d.find("div", "nrec").text
            if push_str:
                try:
                    push_count = int(push_str) # 字串轉換為數字
                except ValueError:
                    # 若轉換失敗，可能是"爆"或 "X1", "X2", ...
                    # 若不是, 不做任何事，push_count 保持為 0
                    if push_str == "爆":
                        push_count = 99
                    elif push_str.startswith("X"):
                        push_count = -10
            
            # 取得文章連結及標題
            if d.find("a"): # 有 a 標籤即表示有 超連結 且 文章存在, 未被刪除
                href = d.find("a")["href"]
                title = d.find("a").text

                contents = get_web_page(PTT_URL + href)
                if contents: # 若成功取得超連結內容
                    soup = BeautifulSoup(contents, "html5lib")

                    article_metas=soup.find_all("div", "article-metaline")
                    if article_metas: # 若有抓到 article_metas 即表示有抓到文章訊息(作者,標題,時間), 代表文章沒有被刪除
                        for article_meta in article_metas:
                            all_spans=[span for span in article_meta.children]
                            if all_spans[0].text == "作者": # 作者ID 及 名稱
                                author=all_spans[1].text
                                authorId=author.split(" ", 1)[0].strip()
                                authorName=author.split(" ", 1)[1].strip()
                            elif all_spans[0].text == "標題": # 標題
                                title=all_spans[1].text.strip()
                            elif all_spans[0].text == "時間": # 發文時間
                                publishedTime=all_spans[1].text.strip()

                        content=soup.text.strip()
                        target_split="※ 發信站: 批踢踢實業坊(ptt.cc),"
                        content=content.split(publishedTime)[1].strip() # 擷取 發文時間 後的字串
                        content=content.split(target_split)[0].strip() # 擷取 ※ 發信站: 批踢踢實業坊(ptt.cc), 前的字串
                        content=content.replace('--', '').strip() # 去掉文末 --

                        createdTime=datetime.now() # 建立時間
                        updateTime=datetime.now() # 更新時間

                        all_comments=soup.find_all("div", "push")
                        for comment in all_comments:
                            all_spans=[span for span in comment.children]
                            push_tag=all_spans[0].text.strip()
                            commentId=all_spans[1].text.strip()
                            commentContent=all_spans[2].text.strip()
                            commentTime=all_spans[3].text.strip()

                            articles.append([authorId, 
                                            authorName, 
                                            title, 
                                            publishedTime, 
                                            content, 
                                            PTT_URL + href, 
                                            createdTime,
                                            updateTime,
                                            commentId,
                                            commentContent,
                                            commentTime,
                                            push_tag,
                                            push_count])

    return articles, prev_url

def get_date_list(start, end):
    start = datetime.strptime(start, "%Y-%m-%d")
    end = datetime.strptime(end, "%Y-%m-%d")
    date_list=[]
    day = timedelta(days=1)
    for i in range((end-start).days+1):
        adjustMD=(start + day*i).strftime("%Y/%m/%d")[5:] # 將日期轉為字串, 再捨棄年 ( 如 : 2020/03/26 -> 03/26 )
        if adjustMD.startswith("0"): # 去掉開頭的 "0" 以符合 PTT 文章日期格式
            adjustMD=adjustMD[1:]
        date_list.append(adjustMD)

    return date_list



if __name__ == "__main__":
    Board = sys.argv[1]
    Start = sys.argv[2]
    End = sys.argv[3]

    date_list=get_date_list(Start, End) # 取得範圍日期

    current_page = get_web_page(PTT_URL + "/bbs/" + Board + "/index.html")
    if current_page:
        articles = [] # 範圍時間內文章
        current_articles, prev_url = get_articles(current_page, date_list)  # 目前頁面範圍時間內的文章
        while current_articles: # 若目前頁面有今日文章，就回到上一頁繼續尋找是否有範圍時間內的文章
            articles += current_articles
            current_page = get_web_page(PTT_URL + prev_url)
            current_articles, prev_url = get_articles(current_page, date_list)

        df=pandas.DataFrame(articles, columns=["authorId", 
                                               "authorName", 
                                               "title", 
                                               "publishedTime", 
                                               "content", 
                                               "canonicalUrl", 
                                               "createdTime",
                                               "updateTime",
                                               "commentId",
                                               "commentContent",
                                               "commentTime",
                                               "push_tag",
                                               "push_count"])

        df.to_csv(datetime.now().strftime("%Y%m%d") + "_" + Board + ".csv", encoding='utf_8_sig')