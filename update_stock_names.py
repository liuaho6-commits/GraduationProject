import akshare as ak

# 1. 直接获取全量 A 股股票代码和简称的对照关系
# 这行代码会返回一个包含 'code' 和 'name' 的 DataFrame
mapping_df = ak.stock_info_a_code_name()

# 2. 查看获取到的数据预览
mapping_df.to_csv("stock_mapping.csv", index=False, encoding="utf_8_sig")