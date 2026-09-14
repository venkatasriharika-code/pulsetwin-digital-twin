import os
os.environ["PULSETWIN_SQLITE_PATH"] = "/tmp/pulsetwin-m5.db"
from app.data import BASE_CONFIG
from app.reallocation import generate_recommendation

snapshot = {"queueMetrics": {"queueLength": 28}, "resourceUtilization": {"doctors": 97, "beds": 92}, "anomaly": {"surgeProbability": .92}}
recommendation = generate_recommendation(BASE_CONFIG, snapshot)
assert recommendation["resourceActions"]
assert recommendation["shiftRecommendations"][0]["additionalDoctors"] > 0
assert recommendation["status"] == "proposed"
print({"summary": recommendation["summary"], "actions": recommendation["resourceActions"], "currentShift": recommendation["shiftRecommendations"][0]})
