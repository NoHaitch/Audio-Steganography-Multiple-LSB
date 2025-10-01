def generate_random_position(seed: str, limit: int) -> int:
    """
    Generate random start position using LCG algorithm

    Args:
        seed (str): string used for seed
        limit (int): the maximum value of the randomized number

    Returns:
        int: the random starting postion generated
    """
    a = 1664525
    c = 1013904223
    m = 2**32

    integer_seed = 0
    for char in seed:
        integer_seed += ord(char)

    next_state = (a * integer_seed + c) % m

    return next_state % limit
