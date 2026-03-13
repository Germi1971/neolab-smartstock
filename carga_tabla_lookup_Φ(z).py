import math
import pymysql

def norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))

conn = pymysql.connect(
    host="190.228.29.65",
    user="neolab",
    password="MYsql437626#",
    database="neobd"
)

cur = conn.cursor()

for i in range(0, 301):   # 0.00 a 3.00
    z = round(i / 100, 2)
    phi = norm_cdf(z)
    cur.execute(
        "INSERT INTO norm_cdf_lut (z, phi) VALUES (%s, %s)",
        (z, phi)
    )

conn.commit()
cur.close()
conn.close()
