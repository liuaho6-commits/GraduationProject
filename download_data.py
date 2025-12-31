import baostock as bs
import pandas as pd
import os
from tqdm import tqdm

# 路径配置
output_dir = "E:/GraduationProject/raw_data"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# 1. 登录系统
bs.login()

# 2. 获取真正的沪深300成分股列表
print("正在获取沪深300成分股名单...")
rs = bs.query_hs300_stocks()
hs300_stocks = []
while (rs.error_code == '0') & rs.next():
    hs300_stocks.append(rs.get_row_data())

# 整理数据：包含 code (股票代码) 和 code_name (股票名称)
stock_df = pd.DataFrame(hs300_stocks, columns=rs.fields)

# --- 保存“白名单” (带股票名字) ---
# 这一步非常重要，spark 入库时要用它来过滤杂鱼股票
stock_mapping = stock_df[['code', 'code_name']].rename(columns={'code_name': 'name'})
stock_mapping.to_csv(f"{output_dir}/stock_basic_info.csv", index=False, encoding="utf_8_sig")
print(f"✅ 沪深300名单已锁定，共 {len(stock_df)} 只，已保存至 stock_basic_info.csv")

# 3. 检查本地文件，查漏补缺
# 获取文件夹里所有的 csv 文件名
local_files = os.listdir(output_dir)
# 计算出我们要下载的列表：在沪深300名单里，且本地还没下载过的
# 注意：如果本地有非沪深300的文件，这里不管它，反正入库时不读
need_download_df = stock_df[~stock_df['code'].apply(lambda x: f"{x}.csv" in local_files)]

print(f"检查本地数据... 需补充下载 {len(need_download_df)} 只成分股。")

# 4. 循环下载
for index, row in tqdm(need_download_df.iterrows(), total=len(need_download_df)):
    stock_code = row['code']
    stock_name = row['code_name']

    try:
        # 下载日线数据
        res = bs.query_history_k_data_plus(stock_code,
                                           "date,code,open,high,low,close,volume,amount,pctChg",
                                           start_date='2020-01-01', end_date='2025-12-31',
                                           frequency="d", adjustflag="3")
        data_list = []
        while (res.error_code == '0') & res.next():
            data_list.append(res.get_row_data())

        if data_list:
            df = pd.DataFrame(data_list, columns=res.fields)
            df.to_csv(f"{output_dir}/{stock_code}.csv", index=False)
    except Exception as e:
        print(f"下载 {stock_name}({stock_code}) 失败: {e}")

bs.logout()
print("\n✅ 下载任务完成！现在你的文件夹里已经包含了所有 HS300 股票。")