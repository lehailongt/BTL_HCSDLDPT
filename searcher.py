from db_function import get_all_feature_from_db
from feature_extractor import *


def search(image_path, top_k):
    # dataset
    images = []
    images.append("data/1.jpg")
    images.append("data/2.jpg")
    images.append("data/3.jpg")
    images.append("data/4.jpg")
    images.append("data/5.jpg")

    query_feature = extract_all_feature(image_path)
    print("query" + "*" * 100)
    print_dict(query_feature)
    all_features = get_all_feature_from_db(5)
    for image_feature in all_features:
        print("*" * 100)
        print_dict(image_feature)
        print("*" * 100)

    results = []

    return images


search("data/1.jpg", 5)


def get_similarty(feature1, feature2):
    return 0.1
