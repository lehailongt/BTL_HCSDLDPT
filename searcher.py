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

    return images
