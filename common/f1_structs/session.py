"""
F1 25 UDP Telemetry — Session Packet (753 bytes).

The session packet has embedded arrays (marshal zones, weather samples)
between scalar fields, so we split into three segments for decoding:

  PACKET_HEADER
  + SESSION_FIELDS_PRE_MARSHAL    (m_weather .. m_numMarshalZones)
  + MARSHAL_ZONE[21]
  + SESSION_FIELDS_MID            (m_safetyCarStatus .. m_numWeatherForecastSamples)
  + WEATHER_FORECAST_SAMPLE[64]
  + SESSION_FIELDS_POST           (m_forecastAccuracy .. m_sector3LapDistanceStart)

Source: F1 25 Telemetry Output Structures (c) 2025 Electronic Arts Inc.
"""

# Marshal zone data
MARSHAL_ZONE = {
    "m_zoneStart": "f",                  # float  - Fraction (0..1) of way through the lap the marshal zone starts
    "m_zoneFlag": "b",                   # int8   - -1 = invalid/unknown, 0 = none, 1 = green, 2 = blue, 3 = yellow
}

# Weather forecast sample
WEATHER_FORECAST_SAMPLE = {
    "m_sessionType": "B",                # uint8  - 0 = unknown, see appendix
    "m_timeOffset": "B",                 # uint8  - Time in minutes the forecast is for
    "m_weather": "B",                    # uint8  - 0 = clear, 1 = light cloud, 2 = overcast, 3 = light rain, 4 = heavy rain, 5 = storm
    "m_trackTemperature": "b",           # int8   - Track temp. in degrees celsius
    "m_trackTemperatureChange": "b",     # int8   - Track temp. change - 0 = up, 1 = down, 2 = no change
    "m_airTemperature": "b",             # int8   - Air temp. in degrees celsius
    "m_airTemperatureChange": "b",       # int8   - Air temp. change - 0 = up, 1 = down, 2 = no change
    "m_rainPercentage": "B",             # uint8  - Rain percentage (0-100)
}

# --- Segment 1: fields before the marshal zones array ---
SESSION_FIELDS_PRE_MARSHAL = {
    "m_weather": "B",                    # uint8  - 0 = clear, 1 = light cloud, 2 = overcast, 3 = light rain, 4 = heavy rain, 5 = storm
    "m_trackTemperature": "b",           # int8   - Track temp. in degrees celsius
    "m_airTemperature": "b",             # int8   - Air temp. in degrees celsius
    "m_totalLaps": "B",                  # uint8  - Total number of laps in this race
    "m_trackLength": "H",               # uint16 - Track length in metres
    "m_sessionType": "B",               # uint8  - 0 = unknown, see appendix
    "m_trackId": "b",                   # int8   - -1 for unknown, see appendix
    "m_formula": "B",                   # uint8  - 0 = F1 Modern, 1 = F1 Classic, 2 = F2, 3 = F1 Generic, 4 = Beta, 6 = Esports, 8 = F1 World, 9 = F1 Elimination
    "m_sessionTimeLeft": "H",           # uint16 - Time left in session in seconds
    "m_sessionDuration": "H",           # uint16 - Session duration in seconds
    "m_pitSpeedLimit": "B",             # uint8  - Pit speed limit in kilometres per hour
    "m_gamePaused": "B",                # uint8  - Whether the game is paused - network game only
    "m_isSpectating": "B",              # uint8  - Whether the player is spectating
    "m_spectatorCarIndex": "B",         # uint8  - Index of the car being spectated
    "m_sliProNativeSupport": "B",       # uint8  - SLI Pro support, 0 = inactive, 1 = active
    "m_numMarshalZones": "B",           # uint8  - Number of marshal zones to follow
}

# --- Segment 2: fields between marshal zones and weather samples ---
SESSION_FIELDS_MID = {
    "m_safetyCarStatus": "B",           # uint8  - 0 = no safety car, 1 = full, 2 = virtual, 3 = formation lap
    "m_networkGame": "B",               # uint8  - 0 = offline, 1 = online
    "m_numWeatherForecastSamples": "B", # uint8  - Number of weather samples to follow
}

# --- Segment 3: fields after the weather samples array ---
SESSION_FIELDS_POST = {
    "m_forecastAccuracy": "B",          # uint8  - 0 = Perfect, 1 = Approximate
    "m_aiDifficulty": "B",             # uint8  - AI difficulty - 0-110
    "m_seasonLinkIdentifier": "I",     # uint32 - Identifier for season - persists across saves
    "m_weekendLinkIdentifier": "I",    # uint32 - Identifier for weekend - persists across saves
    "m_sessionLinkIdentifier": "I",    # uint32 - Identifier for session - persists across saves
    "m_pitStopWindowIdealLap": "B",    # uint8  - Ideal lap to pit on for current strategy (player)
    "m_pitStopWindowLatestLap": "B",   # uint8  - Latest lap to pit on for current strategy (player)
    "m_pitStopRejoinPosition": "B",    # uint8  - Predicted position to rejoin at (player)
    "m_steeringAssist": "B",           # uint8  - 0 = off, 1 = on
    "m_brakingAssist": "B",            # uint8  - 0 = off, 1 = low, 2 = medium, 3 = high
    "m_gearboxAssist": "B",            # uint8  - 1 = manual, 2 = manual & suggested gear, 3 = auto
    "m_pitAssist": "B",                # uint8  - 0 = off, 1 = on
    "m_pitReleaseAssist": "B",         # uint8  - 0 = off, 1 = on
    "m_ERSAssist": "B",                # uint8  - 0 = off, 1 = on
    "m_DRSAssist": "B",                # uint8  - 0 = off, 1 = on
    "m_dynamicRacingLine": "B",        # uint8  - 0 = off, 1 = corners only, 2 = full
    "m_dynamicRacingLineType": "B",    # uint8  - 0 = 2D, 1 = 3D
    "m_gameMode": "B",                 # uint8  - Game mode id - see appendix
    "m_ruleSet": "B",                  # uint8  - Ruleset - see appendix
    "m_timeOfDay": "I",                # uint32 - Local time of day - minutes since midnight
    "m_sessionLength": "B",            # uint8  - 0 = None, 2 = Very Short, 3 = Short, 4 = Medium, 5 = Medium Long, 6 = Long, 7 = Full
    "m_speedUnitsLeadPlayer": "B",             # uint8  - 0 = MPH, 1 = KPH
    "m_temperatureUnitsLeadPlayer": "B",       # uint8  - 0 = Celsius, 1 = Fahrenheit
    "m_speedUnitsSecondaryPlayer": "B",        # uint8  - 0 = MPH, 1 = KPH
    "m_temperatureUnitsSecondaryPlayer": "B",  # uint8  - 0 = Celsius, 1 = Fahrenheit
    "m_numSafetyCarPeriods": "B",              # uint8  - Number of safety cars called during session
    "m_numVirtualSafetyCarPeriods": "B",       # uint8  - Number of virtual safety cars called
    "m_numRedFlagPeriods": "B",                # uint8  - Number of red flags called during session
    "m_equalCarPerformance": "B",              # uint8  - 0 = Off, 1 = On
    "m_recoveryMode": "B",                     # uint8  - 0 = None, 1 = Flashbacks, 2 = Auto-recovery
    "m_flashbackLimit": "B",                   # uint8  - 0 = Low, 1 = Medium, 2 = High, 3 = Unlimited
    "m_surfaceType": "B",                      # uint8  - 0 = Simplified, 1 = Realistic
    "m_lowFuelMode": "B",                      # uint8  - 0 = Easy, 1 = Hard
    "m_raceStarts": "B",                       # uint8  - 0 = Manual, 1 = Assisted
    "m_tyreTemperature": "B",                  # uint8  - 0 = Surface only, 1 = Surface & Carcass
    "m_pitLaneTyreSim": "B",                   # uint8  - 0 = On, 1 = Off
    "m_carDamage": "B",                        # uint8  - 0 = Off, 1 = Reduced, 2 = Standard, 3 = Simulation
    "m_carDamageRate": "B",                    # uint8  - 0 = Reduced, 1 = Standard, 2 = Simulation
    "m_collisions": "B",                       # uint8  - 0 = Off, 1 = Player-to-Player Off, 2 = On
    "m_collisionsOffForFirstLapOnly": "B",     # uint8  - 0 = Disabled, 1 = Enabled
    "m_mpUnsafePitRelease": "B",               # uint8  - 0 = On, 1 = Off (Multiplayer)
    "m_mpOffForGriefing": "B",                 # uint8  - 0 = Disabled, 1 = Enabled (Multiplayer)
    "m_cornerCuttingStringency": "B",          # uint8  - 0 = Regular, 1 = Strict
    "m_parcFermeRules": "B",                   # uint8  - 0 = Off, 1 = On
    "m_pitStopExperience": "B",                # uint8  - 0 = Automatic, 1 = Broadcast, 2 = Immersive
    "m_safetyCar": "B",                        # uint8  - 0 = Off, 1 = Reduced, 2 = Standard, 3 = Increased
    "m_safetyCarExperience": "B",              # uint8  - 0 = Broadcast, 1 = Immersive
    "m_formationLap": "B",                     # uint8  - 0 = Off, 1 = On
    "m_formationLapExperience": "B",           # uint8  - 0 = Broadcast, 1 = Immersive
    "m_redFlags": "B",                         # uint8  - 0 = Off, 1 = Reduced, 2 = Standard, 3 = Increased
    "m_affectsLicenceLevelSolo": "B",          # uint8  - 0 = Off, 1 = On
    "m_affectsLicenceLevelMP": "B",            # uint8  - 0 = Off, 1 = On
    "m_numSessionsInWeekend": "B",             # uint8  - Number of sessions in following array
    "m_weekendStructure": "12B",               # uint8[12] - List of session types for weekend structure - see appendix
    "m_sector2LapDistanceStart": "f",          # float  - Distance in m around track where sector 2 starts
    "m_sector3LapDistanceStart": "f",          # float  - Distance in m around track where sector 3 starts
}

# ---------------------------------------------------------------------------
# 2026 Season Pack (packet format 2026): the session packet gains active aero
# and DRS zone lists plus assist settings, appended after SESSION_FIELDS_POST.
# Split across segments so each embedded array decodes on its own.
# Source: 2026 Season Pack Telemetry Output Structures (c) 2026 Electronic Arts Inc.
# ---------------------------------------------------------------------------

# Active aero zone (start and end as a fraction of the lap)
ACTIVE_AERO_ZONE = {
    "m_zoneStart": "f",                       # float - Fraction (0..1) of the lap the zone starts
    "m_zoneEnd": "f",                         # float - Fraction (0..1) of the lap the zone ends
}

# DRS zone (start and end as a fraction of the lap)
DRS_ZONE = {
    "m_zoneStart": "f",                       # float - Fraction (0..1) of the lap the zone starts
    "m_zoneEnd": "f",                         # float - Fraction (0..1) of the lap the zone ends
}

# --- Segment 4: 2026 fields before the full-throttle active aero zones array ---
SESSION_2026_AERO_FULL_HEAD = {
    "m_activeAeroTrackStatus": "B",            # uint8 - 0 = Full, 1 = Partial
    "m_numActiveAeroZonesFull": "B",           # uint8 - Number of full active aero zones to follow
}

# --- Segment 5: 2026 fields before the partial active aero zones array ---
SESSION_2026_AERO_PARTIAL_HEAD = {
    "m_numActiveAeroZonesPartial": "B",        # uint8 - Number of partial active aero zones to follow
}

# --- Segment 6: 2026 fields before the DRS zones array ---
SESSION_2026_DRS_HEAD = {
    "m_numDRSZones": "B",                      # uint8 - Number of DRS zones to follow
}

# --- Segment 7: 2026 trailing scalar fields ---
SESSION_2026_POST_ZONES = {
    "m_startReactionTime": "f",                # float - Driver start reaction time in seconds (0.0 if assisted)
    "m_antiLockBrakesAssist": "B",             # uint8 - 0 = Off, 1 = On
    "m_tractionControlAssist": "B",            # uint8 - 0 = Off, 1 = Medium, 2 = Full
    "m_dynamicRacingLineHiVis": "B",           # uint8 - 0 = Off, 1 = On
    "m_dynamicRacingLineColourBlind": "B",     # uint8 - 0 = Off, 1 = Protanopia, 2 = Deuteranopia, 3 = Tritanopia
    "m_recurringRewindPrompt": "B",            # uint8 - 0 = Off, 1 = On
}
