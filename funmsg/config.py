class Config:
    '''Bot configuration'''

    # provie a min and max number of messages before the
    # bot submits the "fun" message
    active_msg_count = (5,10) # (min #, max #)

    # id of the channel to monitor
    monitor_channel_id = 916943158699491378

    # number of seconds after last message to "expire" activity counter
    expires = 75 # must be in seconds