-- Tỷ giá USD theo ngày cho mọi tiền tệ của các profile. USD = 1.
-- Ưu tiên tra đúng ngày qua khóa chính 'CUR-YYYYMMDD'; nếu thiếu (hoặc nguồn có dòng nhưng tỷ giá NULL) thì lấy tỷ giá gần nhất trước đó.

DELETE FROM {mart}.fx_daily WHERE date_key BETWEEN :start AND :end;

INSERT INTO {mart}.fx_daily (date_key, currency_code, rate_usd)
SELECT d.date_key, c.currency_code,
       CASE WHEN c.currency_code = 'USD' THEN 1
            ELSE COALESCE(
              (SELECT e.exchange_rate_usd FROM {stg}.exchange_rate_usd e
                WHERE e.id = CONCAT(c.currency_code, '-', DATE_FORMAT(d.date_key, '%Y%m%d'))),
              (SELECT e.exchange_rate_usd FROM {stg}.exchange_rate_usd e
                WHERE e.currency_code = c.currency_code AND e.date <= d.date_key
                  AND e.exchange_rate_usd IS NOT NULL
                ORDER BY e.date DESC LIMIT 1))
       END
FROM {mart}.dim_date d
CROSS JOIN (SELECT DISTINCT currency_code FROM {mart}.dim_account
            WHERE currency_code IS NOT NULL
            UNION SELECT 'USD' UNION SELECT 'CAD' UNION SELECT 'AUD' UNION SELECT 'MXN') c
WHERE d.date_key BETWEEN :start AND :end;
