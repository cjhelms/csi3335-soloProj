import datetime

day = datetime.timedelta(seconds=86400)
d = datetime.timedelta(seconds=64800)
if day < d + d:
    print("less")
