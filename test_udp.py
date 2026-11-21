import argparse
import socket
import struct

# Listen on the loopback interface by default. Use --host 0.0.0.0 to receive packets from another machine.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 20777

HEADER_STRUCT = struct.Struct("<HBBBBBQfIIBB")

PACKET_NAMES = {
    0: "Motion",
    1: "Session",
    2: "Lap Data",
    3: "Event",
    4: "Participants",
    5: "Car Setups",
    6: "Car Telemetry",
    7: "Car Status",
    8: "Final Classification",
    9: "Lobby Info",
    10: "Car Damage",
    11: "Session History",
    12: "Tyre Sets",
    13: "Motion Ex",
}

parser = argparse.ArgumentParser(description="Print the header of each F1 25 UDP telemetry packet")
parser.add_argument(
    "--host",
    default=DEFAULT_HOST,
    help="Bind address. Use 0.0.0.0 to receive packets from another machine (console or PC).",
)
parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="UDP port to listen on")
args = parser.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((args.host, args.port))

print("Listening on", sock.getsockname())

while True:
    data, addr = sock.recvfrom(4096)

    if len(data) < HEADER_STRUCT.size:
        continue

    (
        packet_format,
        game_year,
        game_major,
        game_minor,
        packet_version,
        packet_id,
        session_uid,
        session_time,
        frame_id,
        overall_frame_id,
        player_car_index,
        secondary_player_car_index,
    ) = HEADER_STRUCT.unpack_from(data, 0)

    print(
        f"From {addr} | "
        f"Packet={PACKET_NAMES.get(packet_id, packet_id)} | "
        f"Format={packet_format} | "
        f"SessionTime={session_time:.2f}s | "
        f"Frame={frame_id}"
    )
