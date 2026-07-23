'''
Author: NirvIucE 1750682685@qq.com
Date: 2026-07-23 21:11:40
LastEditors: NirvIucE 1750682685@qq.com
LastEditTime: 2026-07-23 21:14:00
FilePath: \new-picture-train\backend\src\main.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
from fastapi import FastAPI

app = FastAPI(title = "猫里奥云图库", version = "1.0.0")

@app.get("/health")
def health_check():
    """
    健康检查接口
    """
    return {"status":"ok", "version":"maoliao is running"}
