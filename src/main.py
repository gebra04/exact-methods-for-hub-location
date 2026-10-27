from build import build_problem


def main():
    B = []
    for _ in range(25):
        B.append(10)

    build_problem("datasets/CAB25.txt", 1, 2, B, 1.0, 1.0, 1.0)


if __name__ == "__main__":
    main()
