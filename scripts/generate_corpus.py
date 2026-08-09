#!/usr/bin/env python3
"""Generate a large synthetic Arduino corpus for vector index benchmarking.

The hand-written corpus in data/arduino-basics.jsonl is 1010 chunks, which is
enough for Cosmos DB to build quantizedFlat and diskANN indexes but far too
small for diskANN's graph structure to pay off. This produces tens of thousands
of chunks so the crossover point can actually be measured.

    python3 scripts/generate_corpus.py --count 50000

Text is assembled combinatorially from domain vocabulary rather than duplicated,
because near-identical vectors would cluster in embedding space and make an
index comparison meaningless. It is realistic enough to benchmark against and
is not a substitute for the hand-written corpus in retrieval quality.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from pathlib import Path

COMPONENTS = [
    "an Arduino Uno", "a Nano", "a Mega 2560", "an ESP32", "a Pro Mini", "a Leonardo",
    "an ATtiny85", "a Raspberry Pi Pico", "an MKR WiFi board", "a Nano 33 BLE",
    "a DHT22 sensor", "a DS18B20 probe", "an HC-SR04 rangefinder", "a PIR detector",
    "an MPU6050", "a BMP280", "an SSD1306 OLED", "a 16x2 character LCD", "a WS2812 strip",
    "an SG90 servo", "a NEMA17 stepper", "an L298N driver", "a TB6612FNG driver",
    "a relay module", "an HC-05 Bluetooth module", "an nRF24L01 radio", "a LoRa module",
    "an SD card module", "a DS3231 clock", "an MFRC522 reader", "a load cell amplifier",
    "a soil moisture probe", "an MQ-2 gas sensor", "a rotary encoder", "a piezo buzzer",
    "a photoresistor", "a thermistor", "a TMP36", "a shift register", "an I2C multiplexer",
    "a level shifter", "a buck converter", "a lithium charging board", "a solar panel",
    "an optocoupler", "a MOSFET switch", "a current sensor", "a flow meter",
    "a reed switch", "a limit switch", "a capacitive touch pad", "a matrix keypad",
    "an e-paper display", "a TFT screen", "a MAX7219 matrix", "a DFPlayer module",
    "a GPS receiver", "a magnetometer", "an ADS1115 converter", "an MCP4725 DAC",
]

SYMPTOMS = [
    "resets intermittently", "reports values that drift over hours", "draws far more current than expected",
    "stops responding after a few minutes", "returns zero on every read", "returns its maximum value constantly",
    "works on USB but fails on battery", "behaves differently once enclosed", "produces garbled serial output",
    "misses events under load", "runs hot to the touch", "fails only in cold weather",
    "loses its configuration at power-off", "responds slowly to input changes", "triggers spuriously at night",
    "reads correctly only above freezing", "disconnects from the network repeatedly", "corrupts its stored log",
    "jitters when idle", "stalls under mechanical load", "overshoots its target and oscillates",
    "shows readings that lag reality by seconds", "works alone but not alongside other devices",
    "fails after several hours of continuous operation", "reports impossible values occasionally",
    "drops characters during transmission", "cannot be detected on the bus", "flickers visibly",
    "moves to one extreme and holds there", "hums without turning", "reads differently on each power cycle",
]

CAUSES = [
    "an inadequate power supply sagging under load", "a missing decoupling capacitor near the chip",
    "a floating input with no pull-up fitted", "grounds that were never joined between supplies",
    "insufficient SRAM once buffers are allocated", "a blocking delay starving the main loop",
    "an interrupt handler that runs too long", "a baud rate mismatch between the two ends",
    "the absence of a flyback diode across an inductive load", "cable capacitance rounding the signal edges",
    "an address collision between two identical devices", "a wire long enough to act as an antenna",
    "self-heating biasing the measurement upward", "integer overflow in the timing arithmetic",
    "a watchdog firing before the loop completes", "thermal shutdown in the regulator",
    "current draw exceeding what a pin can supply", "an unshielded run beside mains wiring",
    "a breadboard contact that has lost its spring", "EEPROM write endurance being exhausted",
    "the analog multiplexer needing time to settle", "clock drift from a ceramic resonator",
    "a library caching a value it should re-read", "shared timer resources conflicting",
    "voltage sag during a radio transmission burst", "condensation forming inside the enclosure",
    "a cold solder joint that conducts unreliably", "the sensor measuring its own microclimate",
]

REMEDIES = [
    "adding bulk capacitance across the supply", "powering the load from its own regulator",
    "enabling the internal pull-up on that pin", "joining the grounds at a single common point",
    "moving constant strings into flash", "replacing the delay with a millis comparison",
    "reducing the handler to setting a flag", "matching the configured speed at both ends",
    "fitting a diode across the coil", "lowering the bus speed", "readdressing one of the devices",
    "shortening the run and twisting it with its ground", "energising the sensor only while reading",
    "widening the accumulator to an unsigned long", "feeding the watchdog inside the long operation",
    "adding a heat sink and lowering the input voltage", "driving the load through a MOSFET",
    "routing the signal away from the mains run", "soldering the circuit onto perfboard",
    "writing only when the value has actually changed", "discarding the first reading after a channel change",
    "synchronising against a real-time clock", "declaring the shared variable volatile",
    "reconfiguring the peripheral onto a free timer", "adding a capacitor local to the radio module",
    "venting the enclosure with a waterproof membrane", "reflowing the suspect joint",
    "relocating the sensor away from the heat source",
]

CONTEXTS = [
    "in a greenhouse controller", "in a battery-powered sensor node", "on a line-following robot",
    "inside a weather station", "in a workshop dust extractor", "on a model railway layout",
    "in an aquarium monitor", "on a 3D printer", "in a garage door opener", "in a plant watering rig",
    "inside a wearable prototype", "on a self-balancing robot", "in a home energy monitor",
    "in a beehive scale", "on a camera slider", "in an escape room prop", "in a reflow oven controller",
    "on a CNC gantry", "in a rain gauge", "in a pet feeder", "on a quadruped walker",
    "in a fermentation chamber", "in an air quality monitor", "on a solar tracker",
    "in a door access panel", "in a time-lapse intervalometer", "in a MIDI controller",
    "in a high-altitude balloon payload", "in a noise level logger", "on an interactive art installation",
]

TEMPLATES = [
    "When {component} {symptom} {context}, the cause is usually {cause}. The fix is {remedy}, which addresses the underlying condition rather than the symptom.",
    "A common failure {context} is that {component} {symptom}. This is generally traced to {cause}, and is resolved by {remedy}.",
    "Using {component} {context} occasionally leads to a situation where it {symptom}. Investigating usually reveals {cause}, at which point {remedy} restores normal behaviour.",
    "If {component} {symptom} {context}, suspect {cause} before rewriting any code. Confirming it takes minutes, and {remedy} is the standard correction.",
    "{component} that {symptom} {context} is a recognisable pattern. The mechanism is {cause}, and the accepted remedy is {remedy}.",
    "Deploying {component} {context} exposes a failure mode where it {symptom}. Because {cause} is responsible, {remedy} is more effective than adjusting thresholds.",
    "Reports of {component} that {symptom} {context} nearly always come back to {cause}. Once identified, {remedy} resolves it permanently.",
    "One reason {component} {symptom} {context} is {cause}. This is easy to overlook because the symptom appears intermittently, and {remedy} is the durable answer.",
    "Diagnosing {component} that {symptom} {context} starts with ruling out {cause}, which accounts for most cases. Where it applies, {remedy} is sufficient.",
    "It is worth knowing that {component} can {symptom} {context}. The explanation is {cause}, and the remedy that holds up over time is {remedy}.",
]

TOPICS = [
    "power", "sensors", "actuators", "connectivity", "programming", "electronics",
    "timing", "displays", "robotics", "troubleshooting", "storage", "protocols",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=50000)
    parser.add_argument("--output", type=Path, default=Path("data/arduino-synthetic.jsonl"))
    parser.add_argument("--seed", type=int, default=20260804, help="fixed so the corpus is reproducible")
    parser.add_argument("--prefix", default="syn")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)

    space = (
        len(COMPONENTS) * len(SYMPTOMS) * len(CAUSES)
        * len(REMEDIES) * len(CONTEXTS) * len(TEMPLATES)
    )
    if args.count > space:
        sys.exit(f"requested {args.count} exceeds the {space} distinct combinations available")
    print(f"combination space: {space:,}", file=sys.stderr)

    seen: set[tuple] = set()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", encoding="utf-8") as out:
        written = 0
        while written < args.count:
            key = (
                rng.randrange(len(COMPONENTS)), rng.randrange(len(SYMPTOMS)),
                rng.randrange(len(CAUSES)), rng.randrange(len(REMEDIES)),
                rng.randrange(len(CONTEXTS)), rng.randrange(len(TEMPLATES)),
            )
            if key in seen:
                continue
            seen.add(key)

            ci, si, ai, ri, xi, ti = key
            component = COMPONENTS[ci]
            text = TEMPLATES[ti].format(
                component=component, symptom=SYMPTOMS[si], cause=CAUSES[ai],
                remedy=REMEDIES[ri], context=CONTEXTS[xi],
            )
            # Capitalise where a template opens with the component.
            text = text[0].upper() + text[1:]

            out.write(json.dumps({
                "id": f"{args.prefix}-{written + 1:06d}",
                "topic": TOPICS[written % len(TOPICS)],
                "title": f"{component.split(' ', 1)[-1].capitalize()} {SYMPTOMS[si]}",
                "text": text,
                "synthetic": True,
            }, ensure_ascii=False) + "\n")
            written += 1
            if written % 10000 == 0:
                print(f"  {written:,} generated", file=sys.stderr)

    print(f"wrote {written:,} synthetic chunks to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
