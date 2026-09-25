"""Stage 2 flight computer -- the netlist, as data.

Every entry is (ref, lib_id, value, footprint, {pin_number: net}).  A net named in
NC_NET gets a no-connect marker instead of a label.  Power nets get a power symbol;
everything else gets a global label.  Sources for the non-obvious pin assignments are
in pcb/flight_computer/README.md -- do not "tidy" a pin here without reading it.
"""

NC = "~NC~"

PWR_NETS = {"GND": "power:GND", "+3V3": "power:+3V3", "VBATT": "power:VBATT",
            "VIN": "power:VIN", "VBUS": "power:VBUS"}

# ---------------------------------------------------------------- power sheet
POWER = [
    # Solder pads for an 18 AWG XT30 pigtail, not a board connector.  This was a JST-GH
    # (SM02B-GHS-TB), rated 1 A per contact, carrying docs/14's 4.1 A all-four-stalled case.
    # 0.75 mm^2 = 18 AWG; the XT30 (15 A) lives on the wire, and the wire -- not the PCB --
    # takes the pack lead's pull and vibration.  Pad 1 = VBATT (+), pad 2 = GND (-).
    ("J1", "Connector_Generic:Conn_01x02", "2S pack: XT30 pigtail, 18 AWG",
     "Connector_Wire:SolderWire-0.75sqmm_1x02_P4.8mm_D1.25mm_OD2.3mm",
     {"1": "VBATT", "2": "SERVO_GND"}),
    # STAR GROUND.  Servo return current used to come back through the GND planes, and at DC
    # (a stall, or servos holding against aero load) a plane return spreads by resistance
    # instead of running under the VBATT trunk: scripts/pcb_sim_report.py put ~25 mgauss at
    # the magnetometer at 4.1 A against an 18.0 mgauss allowance.  So the servo return is
    # its own net, drawn by finish.py as a 2.0 mm trace beside/under the trunk, and meets GND
    # at exactly one point: NT1, at the pack's negative pad.  Logic GND reaches the pack
    # through NT1; servo current never enters the planes.
    ("NT1", "Device:NetTie_2", "star: SERVO_GND-GND",
     "NetTie:NetTie-2_SMD_Pad0.5mm", {"1": "SERVO_GND", "2": "GND"}),
    # C1 is the servo rail's bulk cap, so it returns on SERVO_GND: servo transients close
    # their loop through C1 locally instead of through the planes.
    ("C1", "Device:C", "22uF/25V", "Capacitor_SMD:C_1210_3225Metric",
     {"1": "VBATT", "2": "SERVO_GND"}),
    # Was "100uF/25V": no such 1210 MLCC exists (100 uF in 1210 stops at 10 V).  22 uF/25 V
    # is honest about its rating; X5R at 8.4 V keeps ~12 uF, so C1 + C2 are ~25 uF of bulk.
    ("C2", "Device:C", "22uF/25V", "Capacitor_SMD:C_1210_3225Metric",
     {"1": "VBATT", "2": "GND"}),
    ("FB1", "Device:FerriteBead_Small", "600R@100MHz 2A",
     "Inductor_SMD:L_0805_2012Metric", {"1": "VBATT", "2": "VIN"}),
    ("C3", "Device:C", "10uF/25V", "Capacitor_SMD:C_0805_2012Metric",
     {"1": "VIN", "2": "GND"}),
    ("C4", "Device:C", "100nF/50V", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "VIN", "2": "GND"}),
    ("U1", "Regulator_Switching:TPS62162DSG", "TPS62162DSGT",
     "Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm",
     {"1": "GND", "2": "VIN", "3": "EN_3V3", "4": "GND", "5": "GND",
      "6": "+3V3", "7": "SW_3V3", "8": "PGOOD", "9": "GND"}),
    ("L1", "Device:L", "2.2uH", "Inductor_SMD:L_1210_3225Metric",
     {"1": "SW_3V3", "2": "+3V3"}),
    ("C5", "Device:C", "22uF/16V", "Capacitor_SMD:C_0805_2012Metric",
     {"1": "+3V3", "2": "GND"}),
    ("C6", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "+3V3", "2": "GND"}),
    ("R1", "Device:R", "100k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "VIN", "2": "EN_3V3"}),
    ("R2", "Device:R", "100k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "+3V3", "2": "PGOOD"}),
    # bench-power path: default OPEN, see README
    ("D1", "Device:D_Schottky", "SS14", "Diode_SMD:D_SOD-123",
     {"2": "VBUS", "1": "VUSB_SW"}),
    ("JP1", "Jumper:SolderJumper_2_Open", "USB->VIN (open)",
     "Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm",
     {"1": "VUSB_SW", "2": "VIN"}),
    ("R3", "Device:R", "1k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "+3V3", "2": "LED_PWR"}),
    ("D2", "Device:LED", "green", "LED_SMD:LED_0603_1608Metric",
     {"2": "LED_PWR", "1": "GND"}),
    ("TP1", "Connector:TestPoint", "VBATT", "TestPoint:TestPoint_Pad_D1.5mm",
     {"1": "VBATT"}),
    ("TP2", "Connector:TestPoint", "+3V3", "TestPoint:TestPoint_Pad_D1.5mm",
     {"1": "+3V3"}),
    ("TP3", "Connector:TestPoint", "GND", "TestPoint:TestPoint_Pad_D1.5mm",
     {"1": "GND"}),
] + [
    # M2.5 through the sled plate; corners of the 70 x 45 outline.
    ("MH%d" % i, "Mechanical:MountingHole", "M2.5",
     "MountingHole:MountingHole_2.7mm_M2.5", {}) for i in (1, 2, 3, 4)
]
# Rails with no power-output pin anywhere on them need a PWR_FLAG or ERC calls
# every power-input pin on them undriven.  VDDA is fed through FB2 from +3V3, and a
# ferrite bead is passive, so the analogue rail needs its own flag.
POWER_FLAGS = ["GND", "+3V3", "VBATT", "VIN", "VBUS", "VDDA", "VIN_IMU"]   # VIN_IMU: behind R33

# ------------------------------------------------------------------ mcu sheet
MCU_PINS = {
    "1": "+3V3",            # VBAT
    "2": "PGOOD",           # PC13
    "3": NC, "4": NC,       # PC14/PC15 -- LSE, unused
    "5": "OSC_IN", "6": "OSC_OUT",
    "7": "NRST",
    "8": "IMU_INT1",        # PC0
    "9": "MAG_INT",         # PC1
    "10": "GNSS_TIMEPULSE",  # PC2
    "11": "GNSS_RESET",     # PC3
    "12": "GND",            # VSSA
    "13": "VDDA",
    "14": NC, "15": NC,     # PA0/PA1
    "16": "DBG_TX",         # PA2  USART2_TX
    "17": "DBG_RX",         # PA3  USART2_RX
    "18": "GND", "19": "+3V3",
    "20": "CS1_IMU",        # PA4
    "21": "SPI1_SCK",       # PA5
    "22": "SPI1_MISO",      # PA6
    "23": "SPI1_MOSI",      # PA7
    "24": NC, "25": NC, "26": NC, "27": NC, "28": NC, "29": NC, "30": NC,
    "31": "VCAP1", "32": "+3V3",
    "33": "CS2_MAG",        # PB12
    "34": "SPI2_SCK",       # PB13
    "35": "SPI2_MISO",      # PB14
    "36": "SPI2_MOSI",      # PB15
    "37": NC,               # PC6
    "38": "CS3_BARO",       # PC7
    "39": "LED_STAT",       # PC8
    "40": NC, "41": NC,     # PC9 / PA8
    "42": "GNSS_RXD",       # PA9  USART1_TX -> receiver RXD
    "43": "GNSS_TXD",       # PA10 USART1_RX <- receiver TXD
    "44": "USB_DM",         # PA11
    "45": "USB_DP",         # PA12
    "46": "SWDIO",          # PA13
    "47": "VCAP2", "48": "+3V3",
    "49": "SWCLK",          # PA14
    "50": NC,               # PA15
    "51": "SPI3_SCK",       # PC10
    "52": "SPI3_MISO",      # PC11
    "53": "SPI3_MOSI",      # PC12
    "54": NC,               # PD2
    "55": "SWO",            # PB3
    "56": NC,               # PB4
    "57": "CS4_FLASH",      # PB5
    "58": "SERVO1",         # PB6  TIM4_CH1
    "59": "SERVO2",         # PB7  TIM4_CH2
    "60": "BOOT0",
    "61": "SERVO3",         # PB8  TIM4_CH3
    "62": "SERVO4",         # PB9  TIM4_CH4
    "63": "GND", "64": "+3V3",
}

MCU = [
    ("U2", "MCU_ST_STM32F4:STM32F405RGTx", "STM32F405RGT6",
     "Package_QFP:LQFP-64_10x10mm_P0.5mm", MCU_PINS),
    ("Y1", "Device:Crystal_GND24", "8MHz",
     "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
     {"1": "OSC_IN", "2": "GND", "3": "OSC_OUT", "4": "GND"}),
    ("C7", "Device:C", "12pF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "OSC_IN", "2": "GND"}),
    ("C8", "Device:C", "12pF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "OSC_OUT", "2": "GND"}),
] + [
    ("C%d" % n, "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "+3V3", "2": "GND"}) for n in range(9, 14)
] + [
    ("C14", "Device:C", "4.7uF", "Capacitor_SMD:C_0805_2012Metric",
     {"1": "+3V3", "2": "GND"}),
    ("C15", "Device:C", "2.2uF", "Capacitor_SMD:C_0805_2012Metric",
     {"1": "VCAP1", "2": "GND"}),
    ("C16", "Device:C", "2.2uF", "Capacitor_SMD:C_0805_2012Metric",
     {"1": "VCAP2", "2": "GND"}),
    ("FB2", "Device:FerriteBead_Small", "600R@100MHz",
     "Inductor_SMD:L_0603_1608Metric", {"1": "+3V3", "2": "VDDA"}),
    ("C17", "Device:C", "1uF", "Capacitor_SMD:C_0603_1608Metric",
     {"1": "VDDA", "2": "GND"}),
    ("C18", "Device:C", "10nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "VDDA", "2": "GND"}),
    ("R4", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "BOOT0", "2": "GND"}),
    ("JP2", "Jumper:SolderJumper_2_Open", "BOOT0->3V3 (open)",
     "Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm",
     {"1": "BOOT0", "2": "+3V3"}),
    ("C19", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "NRST", "2": "GND"}),
    ("SW1", "Switch:SW_Push", "reset",
     "Button_Switch_SMD:SW_SPST_TL3342", {"1": "NRST", "2": "GND"}),
    ("J3", "Connector_Generic:Conn_02x05_Odd_Even", "SWD (ARM 10-pin 1.27mm)",
     "Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD",
     {"1": "+3V3", "2": "SWDIO", "3": "GND", "4": "SWCLK", "5": "GND",
      "6": "SWO", "7": NC, "8": NC, "9": "GND", "10": "NRST"}),
    ("J4", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C",
     "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
     {"A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND",
      "A4": "VBUS", "B4": "VBUS", "A9": "VBUS", "B9": "VBUS",
      "A5": "USB_CC1", "B5": "USB_CC2",
      "A6": "USB_DP_CON", "B6": "USB_DP_CON",
      "A7": "USB_DM_CON", "B7": "USB_DM_CON",
      "A8": NC, "B8": NC, "SH": "GND"}),
    ("R5", "Device:R", "5.1k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "USB_CC1", "2": "GND"}),
    ("R6", "Device:R", "5.1k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "USB_CC2", "2": "GND"}),
    ("U3", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6",
     "Package_TO_SOT_SMD:SOT-23-6",
     {"1": "USB_DM_CON", "2": "GND", "3": "USB_DP", "4": "USB_DP_CON",
      "5": "VBUS", "6": "USB_DM"}),
    ("R7", "Device:R", "1k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "+3V3", "2": "LED_STAT_A"}),
    ("D3", "Device:LED", "blue", "LED_SMD:LED_0603_1608Metric",
     {"2": "LED_STAT_A", "1": "LED_STAT"}),
]

# -------------------------------------------------------------- sensors sheet
SENSORS = [
    # ICM-42688-P pinout: DS-000347 rev 1.6 Table 10 -- see README "Pinouts".
    # Pin 7 RESV is "Connect to GND" (mandatory); 2/3/10/11 are "No Connect or
    # Connect to GND" and are left NC.  Do not "tidy" pin 7 back to NC.
    # Both supply pins (5 and 8) on +3V3_IMU, the IMU's own LDO (U9, below) -- not the
    # shared +3V3 that the MCU, flash and GNSS switch on.  Both, not just VDD: the rail is
    # 3.3 V like +3V3, so SPI levels are unchanged, and there is no VDD/VDDIO sequencing
    # question to answer.  (Added 2026-09-24, pcb/README.md.)
    ("U4", "RocketSenior:ICM-42688-P", "ICM-42688-P",
     "Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y",
     {"1": "SPI1_MISO", "2": NC, "3": NC, "4": "IMU_INT1", "5": "+3V3_IMU",
      "6": "GND", "7": "GND", "8": "+3V3_IMU", "9": NC, "10": NC, "11": NC,
      "12": "CS1_IMU", "13": "SPI1_SCK", "14": "SPI1_MOSI"}),
    ("C20", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "+3V3_IMU", "2": "GND"}),
    ("C21", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "+3V3_IMU", "2": "GND"}),
    ("C22", "Device:C", "2.2uF", "Capacitor_SMD:C_0603_1608Metric",
     {"1": "+3V3_IMU", "2": "GND"}),
    # IMU LDO.  Fed from VIN (6.0-8.4 V, 4.6 V on USB via JP1), so the buck's 2.25 MHz
    # ripple and every MCU/flash/GNSS load step on +3V3 never reach the gyro: the LDO
    # sees them only through VIN, and rejects 70 dB at 1 kHz / 40 dB at 1 MHz on top of FB1.
    # LP2985, not the usual gyro LDOs (LP5907, TPS7A20): those stop at 5.5-6 V in, and a
    # full 2S pack is 8.4 V.  TI SLVS522S: 16 V max in, 30 uV rms with 10 nF on BYPASS,
    # >= 2.2 uF out (>= 1 uF effective after DC bias) -- 4.7 uF/25 V 0805 keeps ~3.5 uF at
    # 3.3 V.  ON/OFF tied to VIN ("tie to VIN if unused").  Load is ~1 mA, so ~5 mW.
    #
    # R33 + C30 are an RC pre-filter (10 ohm x ~0.7 uF effective = 23 kHz corner): the buck
    # draws 345 mA power-save pulses at ~1.1 MHz from VIN, and "legacy" LP2985 silicon --
    # which JLC may ship -- has no published rejection up there.  scripts/pcb_sim_report.py
    # showed the LDO passing that ripple through (IMU rail WORSE at MHz than on +3V3); the RC
    # takes ~34 dB off it before the LDO sees it.  10 ohm x 1 mA = 10 mV of headroom.
    ("U9", "Regulator_Linear:LP2985-3.3", "LP2985-33DBVR",
     "Package_TO_SOT_SMD:SOT-23-5",
     {"1": "VIN_IMU", "2": "GND", "3": "VIN_IMU", "4": "IMU_LDO_BP", "5": "+3V3_IMU"}),
    ("R33", "Device:R", "10", "Resistor_SMD:R_0402_1005Metric",
     {"1": "VIN", "2": "VIN_IMU"}),
    ("C30", "Device:C", "1uF", "Capacitor_SMD:C_0603_1608Metric",
     {"1": "VIN_IMU", "2": "GND"}),
    ("C31", "Device:C", "10nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "IMU_LDO_BP", "2": "GND"}),
    ("C32", "Device:C", "4.7uF", "Capacitor_SMD:C_0805_2012Metric",
     {"1": "+3V3_IMU", "2": "GND"}),
    # CS pull-up to the IMU's own rail, not +3V3: it holds CS at the IMU's VDDIO, and it
    # cannot feed the MCU rail into an unpowered IMU through its CS pin.
    ("R8", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "+3V3_IMU", "2": "CS1_IMU"}),

    # Footprint: MEMSIC Rev A p.20 land pattern is 4 pads per side (2.550 mm
    # centre-to-centre both ways, 0.45 x 0.30 pads, 0.5 pitch).  The old
    # _LayoutBorder3x5y footprint was 5+3 per side and would not have soldered.
    # Project-local, not the stock Package_LGA:LGA-16_3x3mm_P0.5mm: identical
    # copper, but the stock one's pad 1 is the top of the LEFT column while the
    # chip's pin 1 is the right end of the TOP row, and correcting that by
    # rotating U5 270 deg wrecks the pad rectangles (0.05 mm gaps).  The local
    # copy renumbers instead, so U5 is placed at 0 deg.  See pcb/README.md.
    ("U5", "RocketSenior:MMC5983MA", "MMC5983MA",
     "RocketSenior:MMC5983MA_LGA-16_3x3mm_P0.5mm",
     {"1": "SPI2_SCK", "2": "+3V3", "3": NC, "4": "CS2_MAG",
      "5": "SPI2_MISO", "6": NC, "7": NC, "8": NC, "9": "GND",
      "10": "MAG_CAP", "11": "GND", "12": NC, "13": "+3V3", "14": NC,
      "15": "MAG_INT", "16": "SPI2_MOSI"}),
    ("C23", "Device:C", "10uF SET/RESET", "Capacitor_SMD:C_0805_2012Metric",
     {"1": "MAG_CAP", "2": "GND"}),
    ("C24", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "+3V3", "2": "GND"}),
    ("C25", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "+3V3", "2": "GND"}),
    ("R9", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "+3V3", "2": "CS2_MAG"}),

    # pins 4 and 5 are BOTH CSB, internally connected -- datasheet table has a
    # merged cell there; the stock KiCad symbol is right.
    ("U6", "RocketSenior:MS5611-01BA03", "MS5611-01BA03",
     "Package_LGA:LGA-8_3x5mm_P1.25mm",
     {"1": "+3V3", "2": "GND", "3": "GND", "4": "CS3_BARO", "5": "CS3_BARO",
      "6": "SPI2_MISO", "7": "SPI2_MOSI", "8": "SPI2_SCK"}),
    ("C26", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "+3V3", "2": "GND"}),
    ("R10", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "+3V3", "2": "CS3_BARO"}),

    # /WP and /HOLD are pulled up rather than strapped to the rail, so either can
    # be driven later without cutting a track.
    ("U7", "Memory_Flash:W25Q128JVS", "W25Q128JVSIQ",
     "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm",
     {"1": "CS4_FLASH", "2": "SPI3_MISO", "3": "FLASH_WP", "4": "GND",
      "5": "SPI3_MOSI", "6": "SPI3_SCK", "7": "FLASH_HOLD", "8": "+3V3"}),
    ("C27", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "+3V3", "2": "GND"}),
    ("R11", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "+3V3", "2": "CS4_FLASH"}),
    ("R12", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "+3V3", "2": "FLASH_WP"}),
    ("R13", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric",
     {"1": "+3V3", "2": "FLASH_HOLD"}),
]

# ------------------------------------------------------------------- io sheet
IO = [
    # CHECKED AGAINST u-blox UBX-20035208 R08 (30-Jan-2026) Table 10, pin for pin.  Every NC
    # here is the datasheet's own instruction, not a guess -- do not "fix" any of them:
    #   5  EXTINT     "Leave open if not used."
    #   6  V_BCKP     backup supply.  On +3V3, i.e. the same rail as VCC, so the backup
    #                 domain dies with the board and EVERY power-up is a cold start.  That is
    #                 accepted, not missed: docs/14 budgets 60 minutes armed on the pad, which
    #                 is many times a cold TTFF.  Wiring it to a coin cell or supercap is the
    #                 change if that ever stops being true.
    #   7  V_IO       IO supply, 3.3 V here.  Range is set by pin 15, below.
    #   8  VCC        main supply.
    #   13 LNA_EN     output, drives an external LNA / active antenna.  Open = passive
    #                 antenna, which is this board's choice (docs/14).
    #   14 VCC_RF     output, would bias an active antenna.  Open for the same reason.  Note
    #                 RF_IN has a built-in DC block (Table 13), so an active antenna would
    #                 need an external bias tee at J5 as well -- it is not a one-wire change.
    #   15 VIO_SEL    "Connect to GND for 1.8 V supply, or LEAVE OPEN for 3.3 V supply."
    #                 OPEN IS THE 3.3 V SETTING AND IS DELIBERATE.  Tying it to GND would
    #                 drop V_IO to 1.8 V and break every interface on this board.
    #   16 SDA / 17 SCL  "Leave open if not used" -- the bus map is SPI + UART, no I2C.
    #   18 SAFEBOOT_N  "Leave open if not used."
    ("U8", "RF_GPS:MAX-M10S", "MAX-M10S", "RF_GPS:ublox_MAX",
     {"1": "GND", "2": "GNSS_TXD", "3": "GNSS_RXD", "4": "GNSS_TIMEPULSE",
      "5": NC, "6": "+3V3", "7": "+3V3", "8": "+3V3", "9": "GNSS_RESET",
      "10": "GND", "11": "GNSS_RF", "12": "GND", "13": NC, "14": NC,
      "15": NC, "16": NC, "17": NC, "18": NC}),
    ("C28", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric",
     {"1": "+3V3", "2": "GND"}),
    ("C29", "Device:C", "10uF", "Capacitor_SMD:C_0805_2012Metric",
     {"1": "+3V3", "2": "GND"}),
    ("J5", "Connector:Conn_Coaxial", "u.FL GNSS ant",
     "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical",
     {"1": "GNSS_RF", "2": "GND"}),
    ("J10", "Connector_Generic:Conn_01x04", "debug UART",
     "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
     {"1": "+3V3", "2": "DBG_TX", "3": "DBG_RX", "4": "GND"}),
] + [
    # Pin 3 is SERVO_GND, not GND: the servo return is a star, joined to GND only at the
    # pack (NT1, power sheet).  See J1 for why.
    ("J%d" % (5 + i), "Connector_Generic:Conn_01x03", "servo %d (raw 2S)" % i,
     "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
     {"1": "SERVO%d" % i, "2": "VBATT", "3": "SERVO_GND"})
    for i in (1, 2, 3, 4)
]

SHEETS = [("power", "Power -- 2S in, 3.3 V logic rail, raw servo rail", POWER),
          ("mcu", "MCU -- STM32F405RGT6, clock, SWD, USB", MCU),
          ("sensors", "Sensors -- IMU / mag / baro / log flash", SENSORS),
          ("io", "I/O -- GNSS, servos, debug UART", IO)]
