import sys
sys.path.insert(0, r"c:\Users\Alumno\Desktop\SMF\revolution-main\REVOLUTION_ENTREGABLE")
from app import calculate_proximity_score
print("Score con 13 estrellas:", calculate_proximity_score(-8.0, 13, "CALM", "MOMENTUM", 49.51))
print("Score con 12 estrellas:", calculate_proximity_score(-8.0, 12, "CALM", "MOMENTUM", 49.51))
