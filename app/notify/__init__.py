"""Gửi bản tóm tắt quảng cáo Amazon + Wayfair hằng ngày cho từng PIC qua Google Chat webhook.

PIC lấy từ phân công nhóm sản phẩm ở backend (staging.prd_product_assigned → ads_mart.map_group_pic). Mỗi PIC có
một space Google Chat riêng với webhook riêng (cfg_pic_notify), vì webhook chỉ gửi được vào space, không nhắn riêng.
"""
