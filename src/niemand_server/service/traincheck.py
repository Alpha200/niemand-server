import aiohttp


class TrainCheckService:
    ARTICLE_MAP = {
        "ABR": "der",
        "S": "die",
        "RE": "der",
        "RB": "die",
        "EC": "der",
        "IC": "der",
        "ICE": "der",
        "U": "die",
        "Bus SEV": "der"
    }

    def __init__(self, station_from, station_via):
        self.station_from = station_from
        self.station_via = station_via

    def get_article(self, train):
        transport_type = train[:train.index(" ")]

        if transport_type not in self.ARTICLE_MAP:
            return ""
        else:
            return self.ARTICLE_MAP[transport_type]

    def fix_one(self, train):
        splitted = train.split(' ')
        number = "eins" if splitted[1] == "1" else splitted[1]

        return f"{splitted[0]} {number}"

    def convert_time(self, time: str):
        hour, minute = time.split(':')
        return f'{hour} Uhr {minute}'

    async def check_train(self):
        url = f'https://dbf.finalrewind.org/{self.station_from}'

        params = dict(
            via=self.station_via,
            mode="json",
            version="3"
        )
        async with aiohttp.ClientSession() as session:
            resp = await session.get(url, params=params)
            data = await resp.json()

        departures = data['departures']

        if len(departures) == 0:
            return 'In nächster Zeit fahren keine Bahnen.'

        result = ""

        for departure in departures[:2]:
            result += "{} {} um {} ".format(
                self.get_article(departure['train']),
                self.fix_one(departure['train']),
                self.convert_time(departure['scheduledDeparture'])
            )

            if departure['isCancelled'] == 0:
                if departure['delayDeparture'] < 3:
                    result += "ist pünktlich. "
                else:
                    result += "hat {} Minuten Verspätung. ".format(
                        departure['delayDeparture']
                    )
                for qos_message in departure['messages']['qos']:
                    result += "{}. ".format(qos_message['text'])

                if departure['platform'] != departure['scheduledPlatform']:
                    result += "Heute von Gleis {}. ".format(departure['platform'])
            else:
                result += "fällt aus. "

        return result
