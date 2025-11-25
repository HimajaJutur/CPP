SCHEDULES = {
    ("Dublin", "Cork"): [
        {"time": "06:30", "arrival": "09:30", "type": "Bus"},
        {"time": "09:00", "arrival": "12:00", "type": "Train"},
        {"time": "14:00", "arrival": "17:00", "type": "Bus"},
        {"time": "18:00", "arrival": "21:00", "type": "Train"},
    ],

    ("Cork", "Dublin"): [
        {"time": "07:00", "arrival": "10:00", "type": "Bus"},
        {"time": "11:00", "arrival": "14:00", "type": "Train"},
        {"time": "16:00", "arrival": "19:00", "type": "Bus"},
    ],

    ("Dublin", "Galway"): [
        {"time": "08:00", "arrival": "11:00", "type": "Bus"},
        {"time": "12:00", "arrival": "15:00", "type": "Train"},
        {"time": "17:00", "arrival": "20:00", "type": "Bus"},
    ],

    ("Galway", "Dublin"): [
        {"time": "09:00", "arrival": "12:00", "type": "Bus"},
        {"time": "13:00", "arrival": "16:00", "type": "Train"},
        {"time": "18:00", "arrival": "21:00", "type": "Bus"},
    ],

    ("Dublin", "Limerick"): [
        {"time": "07:30", "arrival": "10:00", "type": "Train"},
        {"time": "10:00", "arrival": "12:30", "type": "Bus"},
        {"time": "15:00", "arrival": "17:30", "type": "Train"},
    ],

    ("Limerick", "Dublin"): [
        {"time": "06:45", "arrival": "09:15", "type": "Train"},
        {"time": "11:00", "arrival": "13:30", "type": "Bus"},
    ]
}
