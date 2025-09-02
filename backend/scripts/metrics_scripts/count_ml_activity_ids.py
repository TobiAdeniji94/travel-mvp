import pickle
import os

# Try common model paths
possible_paths = [
    '/app/models/item_index_map_act.pkl',
    './models/item_index_map_act.pkl',
    '../models/item_index_map_act.pkl',
    'item_index_map_act.pkl'
]

for path in possible_paths:
    if os.path.exists(path):
        with open(path, 'rb') as f:
            ids = pickle.load(f)
        print(f"Number of activity IDs in ML mapping: {len(ids)}")
        break
else:
    print("item_index_map_act.pkl not found in known locations. Please update the script with the correct path.")
