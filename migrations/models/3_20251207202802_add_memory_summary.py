from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "dialog_sessions" ADD "memory_summary" TEXT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "dialog_sessions" DROP COLUMN "memory_summary";"""


MODELS_STATE = (
    "eJztXG1T2zgQ/isZf4IZjgYnIXBzczMBQpsrLx0Id532Oh7FVhIPfkltuZBj+O8nyW+yLB"
    "vbJMRp/cUoK60lPSutdldrniTT1qDh7t+50JF+bz1JFjAhLiToey0JLBYxlRAQmBi0oYdb"
    "UAqYuMgBKsLEKTBciEkadFVHXyDdtjDV8gyDEG0VN9StWUzyLP27BxVkzyCa04F8/YbJuq"
    "XBR+iGPxf3ylSHhpYYp66RvildQcsFpd3djc7OaUvS3URRbcMzrbj1YonmthU19zxd2yc8"
    "pG4GLegABDVmGmSUwXRDkj9iTECOB6OhajFBg1PgGQQM6Y+pZ6kEgxbtiTy6f0ol4FFti0"
    "CrW4hg8fTszyqeM6VKpKvTD4Obnc7hLp2l7aKZQyspItIzZQQI+KwU1xhIBA04c4CpiBA9"
    "0WcjC4kx5Rg5cPGg1wNrCFc1DPGA8J/fjmW50+nL7c7hUa/b7/eO2ke4LR1SuqqfA/zJ6P"
    "3oakxmauM94O8MQiCYxxirc4BK48swVcI2QC6CNmwSYxtv120GlygiWk6hezoHjhhblocD"
    "F0+onuCa4FExoDVDc/zzoN3OAe7vwQ3VCLjVbhK+q6BK9uuSSCLdhP/ZVikkWZ6tRLJXBM"
    "heNo69FIyqA8l0FYDSQJ7hGgJZxpZPcHJwagHrfliool/fAF08B+3aMpaBbHPQHY8uh7fj"
    "weUnMhPTdb8bFKLBeEhqZEpdctSdQ04S0Uta/4zGH1rkZ+vL9dWQPwqjduMvEhkT8JCtWP"
    "aDAjTmnAmpITDPxACZ3jMnJyFMgHr/ABxNSdQwGwm4965A2wds5x9voAEosGkxBwbYGL+i"
    "ngJ+DldtSI0FHSPgQtfF730lCGc6MOzZrf+uLUODrBNbtrNWTrrKlE2eAiwwo6MmfZOe2M"
    "UhsNrDRZNttUcrc7VW+1d6ogbWCi2Sjsjvb5xB/yTFc4yYSBv4uHDCRRPMP7b1H/33eYFX"
    "Ei4TifLhedAfdAEyb2e0adEOApbifWRO++UOE+2zO2w8oHV7QLwgkpBm2uc822ocoDez0u"
    "WDbr971DnsRsZ5RMmzydP2N9KRUdJkDBgq2YubQCxhMMq9XgGLEbfKNBlpXRJEdmQpKMdY"
    "HYih5Ni2xADPMwmHn8cJazBEbedy8Hk3YRFeXF+9D5szKJ9eXJ9w4EJzAjUNj0iZzKDims"
    "AwyoCcwd6ALQTbVedQ84xK/g/PuwIPqF6A18jhCaed8nhYYTrQJEA5FWTJsTai3LAom6jE"
    "TxSV4OOfQss12xlgWFbpEWx0Q77gAKTiOEkA0+id2w7UZ9ZHuKQYjvA4gKWK7Fbuyqy2qK"
    "ViFJjsgIfItWSXBZ4enhREvik/uD0dnA19X1Qc+1pntCMZBRKEPVJhouz4h0abKmx4qrm/"
    "3Grv3fVMEzjLMgY9w9IY8UIj3oSm7SyVCtimORuIhRAbwEWKifUQVnqCMPlft9dXYoRTjB"
    "zAdxae+VdNV9Fey9Bd9G1dhxKjICaebiDdcvdJh2vSEQSRfCnwgHPKhLyAl4K30CpaxUnO"
    "xireqFWcun9qvJ2fQq6Nt9N4O7+Yt3Oqo6UkcHIofS/Pt1F1pMP1uzSJ+086yAKXnXhsSy"
    "XMuCp2tQoMRJK0ECRsbuFOOLbs7kq5Zpm3gEXv/oIVWIPcx1de/GV7YmWT8F6VgLf5a8BC"
    "GXhyTgaenM7ASy/eon5XmrPxu4R+V5PkuJokR9uzEHb0VXwOlYGS59tKOOUiOz973/NYLu"
    "yFF6fCFTx4kkzblSG+stwTAgDyRCvw3LBBBnIsE4fblHDV8/TJweXs+u7kYtj6dDM8Hd2O"
    "gihJ5LTRSkLCBN03cW+GgwseSduaVYCS5fqlsSyRJ7xO7+HSjwt+0F1kO0I/gmuxl+dRBF"
    "FGZc40fsm1kP712t2DI/LsHtCnTJ4dSMttWvZrp624kV8dPH22Y1ru0acWs3WOW8z7ZP/H"
    "lOGe0AqVlvsM3R9GmxlSL24flI8lbv1s/2xKOnQlUnK51aEwDnUxD4+YVS4C5qJKbzFzdn"
    "+Ni1fpfM1JlaVB75J5sizPRr8SlEZnLX5jBpuR3VQT8VYNdni0VcfB94+8yngbyyczDpqf"
    "r1yLVOVIDq9WdFgmmxVD5peda/usc/Vi6PZTELc3DGuo7BFW5uVun5N8Gw4tUetBZlctYC"
    "2JShZDd1pMJG8dV6Hqpcp3uMqr4oAr82EZS6+jsvp+BUqq4CZa/2cGCaOpzK1ognFTl6JM"
    "wsGVbcF9D6mW/SBIN/BlKTM2eq+IXDuMNsw6/jexXWt0RVso1TjSwmSBlNAGPF8NFEKgvH"
    "21UHUFtHbIZ2LvyMn/Lgwl71bRCasP4wJdwYJf4E4Fksq5bUiy1UBQB5BRvowKDn3q0Gof"
    "jOp5fIaaTVGBYUCBQZm9bQSsdRCIr34nzFnJnJLBBtGYczPYXd1YFQfVvs10mNhRRcX4Bm"
    "fqNieg+jrugJGLyjzbzAF6tPXGak0itAPo6OpcEkRmg5q9vIgsiNvUJm29CZy9HDj7AR1X"
    "eL+XrdYZli3NkFiHtiVbowSIQfPtBHAt/+QJ94igJYiqZGecMyybyjVf233fyrLKN3q8PP"
    "8PAxIANA=="
)
