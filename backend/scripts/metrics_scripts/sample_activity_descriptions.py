import csv
import random
from collections import Counter

CSV_PATH = "activities.csv"  # Adjust path if running from another directory
SAMPLE_SIZE = 20  # Number of random samples to print
MIN_LENGTH = 10


def load_descriptions(csv_path):
    descriptions = []
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            desc = (row.get('description') or '').strip()
            if len(desc) >= MIN_LENGTH:
                descriptions.append(desc)
    return descriptions


def sample_descriptions(descriptions, n=20):
    if len(descriptions) <= n:
        return descriptions
    return random.sample(descriptions, n)


def print_stats(descriptions):
    print(f"Total activities with >= {MIN_LENGTH} chars: {len(descriptions)}")
    unique = set(descriptions)
    print(f"Unique descriptions: {len(unique)}")
    most_common = Counter(descriptions).most_common(5)
    if most_common and most_common[0][1] > 1:
        print("Most common descriptions:")
        for desc, count in most_common:
            if count > 1:
                print(f"  [{count}x] {desc[:80]}{'...' if len(desc) > 80 else ''}")
    else:
        print("No duplicate descriptions found.")


def main():
    descriptions = load_descriptions(CSV_PATH)
    print_stats(descriptions)
    print("\nSample activity descriptions:")
    for desc in sample_descriptions(descriptions, SAMPLE_SIZE):
        print(f"- {desc}")

if __name__ == "__main__":
    main()
