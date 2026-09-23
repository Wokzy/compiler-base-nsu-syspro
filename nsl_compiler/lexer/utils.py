from .vocab import Token, Vocab


def build_raw_bpe_tokens(base: list[Vocab]) -> list[Token]:

    res = []
    # for i in range(256):
    #     if not chr(i) in base:
    #         res.append(Token(
    #             id=base.size + i,
    #             kind="RAW_BPE",
    #             value=chr(i),
    #         ))

    alpahnum = "qwertyuiopasdfghjklzxcvbnm"
    alpahnum += alpahnum.upper()
    alpahnum += "0123456789"

    for i, c in enumerate(alpahnum):
        res.append(
            Token(
                id=base.size + i,
                kind="RAW_BPE",
                value=c,
            )
        )

    return res
