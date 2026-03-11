import time
from data_fetcher import HistoricalDataFetcher

print("Test start")
f = HistoricalDataFetcher()

print("Fetching Bodo Glimt stats...")
t0 = time.time()
stats = f.get_team_stats("Bodo Glimt")
print(f"Stats returned in {time.time() - t0:.2f}s: {stats}")
