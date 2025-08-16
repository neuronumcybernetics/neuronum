import neuronum
import asyncio


cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)


async def main():
    await cell.notify(
        receiver="receiver::cell",
        title="notification_title",
        message="notification_message"
    )

asyncio.run(main())