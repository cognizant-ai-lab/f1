import argparse
import csv
import socket
import struct
import time
from pathlib import Path

# ---- UDP config ----
# Listen on the loopback interface by default. Use --host 0.0.0.0 to receive packets from another machine.
DEFAULT_UDP_HOST = "127.0.0.1"
DEFAULT_UDP_PORT = 20777

# ---- Packet constants (F1 25 spec) ----
PACKET_ID_LAP_DATA = 2  # Lap Data packetId is 2  [oai_citation:3‡EA Forums](https://forums.ea.com/t5/s/tghpe58374/attachments/tghpe58374/f1-games-game-info-hub-en/61/4/Data%20Output%20from%20F1%2025%20v3.pdf)

# PacketHeader (packed, little-endian) from spec  [oai_citation:4‡EA Forums](https://forums.ea.com/t5/s/tghpe58374/attachments/tghpe58374/f1-games-game-info-hub-en/61/4/Data%20Output%20from%20F1%2025%20v3.pdf)
# uint16 m_packetFormat; uint8 m_gameYear; uint8 m_gameMajorVersion; uint8 m_gameMinorVersion;
# uint8 m_packetVersion; uint8 m_packetId; uint64 m_sessionUID; float m_sessionTime;
# uint32 m_frameIdentifier; uint32 m_overallFrameIdentifier; uint8 m_playerCarIndex; uint8 m_secondaryPlayerCarIndex
HEADER_STRUCT = struct.Struct("<HBBBBBQfIIBB")
HEADER_SIZE = HEADER_STRUCT.size  # should be 29 bytes (packed)

# LapData struct is 57 bytes in F1 25 (derived from packet size math; also matches field sizes)  [oai_citation:5‡EA Forums](https://forums.ea.com/t5/s/tghpe58374/attachments/tghpe58374/f1-games-game-info-hub-en/61/4/Data%20Output%20from%20F1%2025%20v3.pdf)
LAPDATA_STRUCT = struct.Struct(
    "<"   # little-endian
    "I"   # m_lastLapTimeInMS
    "I"   # m_currentLapTimeInMS
    "H"   # m_sector1TimeMSPart
    "B"   # m_sector1TimeMinutesPart
    "H"   # m_sector2TimeMSPart
    "B"   # m_sector2TimeMinutesPart
    "H"   # m_deltaToCarInFrontMSPart
    "B"   # m_deltaToCarInFrontMinutesPart
    "H"   # m_deltaToRaceLeaderMSPart
    "B"   # m_deltaToRaceLeaderMinutesPart
    "f"   # m_lapDistance
    "f"   # m_totalDistance
    "f"   # m_safetyCarDelta
    "B"   # m_carPosition
    "B"   # m_currentLapNum
    "B"   # m_pitStatus
    "B"   # m_numPitStops
    "B"   # m_sector
    "B"   # m_currentLapInvalid
    "B"   # m_penalties
    "B"   # m_totalWarnings
    "B"   # m_cornerCuttingWarnings
    "B"   # m_numUnservedDriveThroughPens
    "B"   # m_numUnservedStopGoPens
    "B"   # m_gridPosition
    "B"   # m_driverStatus
    "B"   # m_resultStatus
    "B"   # m_pitLaneTimerActive
    "H"   # m_pitLaneTimeInLaneInMS
    "H"   # m_pitStopTimerInMS
    "B"   # m_pitStopShouldServePen
    "f"   # m_speedTrapFastestSpeed
    "B"   # m_speedTrapFastestLap
)
LAPDATA_SIZE = LAPDATA_STRUCT.size  # should be 57

NUM_CARS = 22

def mmss_parts_to_ms(minutes_part: int, ms_part: int) -> int:
    return minutes_part * 60_000 + ms_part

def ms_to_lapstr(ms: int) -> str:
    if ms <= 0 or ms == 0xFFFFFFFF:
        return ""
    minutes = ms // 60_000
    rem = ms % 60_000
    seconds = rem // 1000
    millis = rem % 1000
    return f"{minutes}:{seconds:02d}.{millis:03d}"

def parse_args() -> argparse.Namespace:
    """Parse the UDP host and port from the command line."""
    parser = argparse.ArgumentParser(description="Log F1 25 lap data from UDP telemetry to a CSV file")
    parser.add_argument(
        "--host",
        default=DEFAULT_UDP_HOST,
        help="Bind address. Use 0.0.0.0 to receive packets from another machine (console or PC).",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_UDP_PORT, help="UDP port to listen on")
    return parser.parse_args()

def main():
    args = parse_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    print(f"Listening on UDP {args.host}:{args.port} ...")

    # Create data directory if it doesn't exist
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    out_path = data_dir / f"f1_25_laps_{int(time.time())}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "wall_time",
                "session_uid",
                "session_time",
                "frame_id",
                "player_car_index",
                "current_lap_num",
                "lap_distance_m",
                "sector",
                "current_lap_time_ms",
                "last_lap_time_ms",
                "last_lap_time_str",
                "position",
                "lap_invalid",
                "penalties_s",
                "num_pit_stops",
                "pit_status",
            ],
        )
        writer.writeheader()

        last_seen_lap_num = None

        while True:
            data, addr = sock.recvfrom(4096)
            if len(data) < HEADER_SIZE:
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

            if packet_id != PACKET_ID_LAP_DATA:
                continue

            # Lap Data packet: header + 22 * LapData + 2 bytes (time trial indices)  [oai_citation:6‡EA Forums](https://forums.ea.com/t5/s/tghpe58374/attachments/tghpe58374/f1-games-game-info-hub-en/61/4/Data%20Output%20from%20F1%2025%20v3.pdf)
            base = HEADER_SIZE + player_car_index * LAPDATA_SIZE
            if len(data) < base + LAPDATA_SIZE:
                continue

            fields = LAPDATA_STRUCT.unpack_from(data, base)
            (
                last_lap_ms,
                current_lap_ms,
                s1_ms, s1_min,
                s2_ms, s2_min,
                dfront_ms, dfront_min,
                dlead_ms, dlead_min,
                lap_dist,
                total_dist,
                sc_delta,
                position,
                current_lap_num,
                pit_status,
                num_pit_stops,
                sector,
                lap_invalid,
                penalties_s,
                total_warnings,
                corner_cut_warnings,
                unserved_dt,
                unserved_sg,
                grid_pos,
                driver_status,
                result_status,
                pit_lane_timer_active,
                pit_lane_time_in_ms,
                pit_stop_timer_in_ms,
                pit_stop_should_serve_pen,
                speedtrap_fastest_speed,
                speedtrap_fastest_lap,
            ) = fields

            # Detect lap completion (lap number increments when you start the next lap)
            if last_seen_lap_num is None:
                last_seen_lap_num = current_lap_num
            elif current_lap_num != last_seen_lap_num:
                # The last completed lap time is in m_lastLapTimeInMS  [oai_citation:7‡EA Forums](https://forums.ea.com/t5/s/tghpe58374/attachments/tghpe58374/f1-games-game-info-hub-en/61/4/Data%20Output%20from%20F1%2025%20v3.pdf)
                print(f"LAP COMPLETED: Lap {last_seen_lap_num} = {ms_to_lapstr(last_lap_ms)}")
                last_seen_lap_num = current_lap_num

            writer.writerow(
                {
                    "wall_time": time.time(),
                    "session_uid": session_uid,
                    "session_time": session_time,
                    "frame_id": frame_id,
                    "player_car_index": player_car_index,
                    "current_lap_num": current_lap_num,
                    "lap_distance_m": lap_dist,
                    "sector": sector,
                    "current_lap_time_ms": current_lap_ms,
                    "last_lap_time_ms": last_lap_ms,
                    "last_lap_time_str": ms_to_lapstr(last_lap_ms),
                    "position": position,
                    "lap_invalid": lap_invalid,
                    "penalties_s": penalties_s,
                    "num_pit_stops": num_pit_stops,
                    "pit_status": pit_status,
                }
            )
            f.flush()

if __name__ == "__main__":
    main()
