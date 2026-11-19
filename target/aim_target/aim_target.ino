// AIM Phase 7 target firmware (Arduino UNO).
//
// Links (docs/icd/ICD.md Section 3):
//   USB serial  115200 baud : ADC1_WORD, SELECTED_ALT, APPROACH_MODE, STEP
//   SoftwareSerial pin 10   : ADC2_WORD, 38400 baud (CP2102 bridge)
//
// The firmware is a thin shell: it latches the most recent input frames and
// runs the verified core (src/aim.c) once per STEP frame, using the host's
// now_ms from the STEP payload. Using host-supplied time (instead of millis())
// makes processor-in-the-loop runs deterministic and comparable cycle-by-cycle
// with the host build. After each step it prints one status line.
#include <SoftwareSerial.h>

extern "C" {
#include "src/aim.h"
#include "framer.h"
}

static const int32_t NO_TARGET = 0x7FFFFFFF;

static SoftwareSerial adc2_link(10, 11);  // RX = 10 (CP2102 TXD), TX unused
static aim_t g_aim;
static aim_framer_t g_main_framer;
static aim_framer_t g_adc2_framer;

static uint32_t g_word_ch1 = 0;
static uint32_t g_word_ch2 = 0;
static int32_t g_selected = 0;
static uint8_t g_selected_valid = 0;
static uint8_t g_approach = 0;

static void emit_status(uint32_t now_ms, const aim_status_t &s)
{
    // S,now,state,approaching,deviation,miscompare,alt_valid,alt,ch1v,ch2v,ch1s,ch2s,sel_valid,rejected
    Serial.print(F("S,"));
    Serial.print(now_ms);                        Serial.print(',');
    Serial.print(s.alerter.state);               Serial.print(',');
    Serial.print(s.alerter.alert_approaching);   Serial.print(',');
    Serial.print(s.alerter.alert_deviation);     Serial.print(',');
    Serial.print(s.monitor.miscompare);          Serial.print(',');
    Serial.print(s.altitude_valid);              Serial.print(',');
    Serial.print(s.altitude_ft);                 Serial.print(',');
    Serial.print(s.monitor.ch1_valid);           Serial.print(',');
    Serial.print(s.monitor.ch2_valid);           Serial.print(',');
    Serial.print(s.monitor.ch1_stale);           Serial.print(',');
    Serial.print(s.monitor.ch2_stale);           Serial.print(',');
    Serial.print(s.alerter.selected_altitude_valid); Serial.print(',');
    Serial.println((uint16_t)(g_main_framer.rejected + g_adc2_framer.rejected));
}

static void handle(const aim_frame_t &f)
{
    switch (f.type) {
    case AIM_FRAME_ADC1_WORD:    g_word_ch1 = f.payload; break;
    case AIM_FRAME_ADC2_WORD:    g_word_ch2 = f.payload; break;
    case AIM_FRAME_SELECTED_ALT:
        g_selected = (int32_t)f.payload;
        g_selected_valid = (uint8_t)(g_selected != NO_TARGET);
        break;
    case AIM_FRAME_APPROACH_MODE: g_approach = (uint8_t)(f.payload != 0u); break;
    case AIM_FRAME_STEP: {
        aim_status_t out;
        aim_step(&g_aim, f.payload, g_word_ch1, g_word_ch2,
                 g_selected, g_selected_valid, g_approach, &out);
        emit_status(f.payload, out);
        break;
    }
    default: break;
    }
}

void setup()
{
    Serial.begin(115200);
    adc2_link.begin(38400);
    adc2_link.listen();
    aim_init(&g_aim);
    aim_framer_init(&g_main_framer);
    aim_framer_init(&g_adc2_framer);
}

void loop()
{
    aim_frame_t f;
    while (Serial.available() > 0) {
        if (aim_framer_push(&g_main_framer, (uint8_t)Serial.read(), &f)) {
            handle(f);
        }
    }
    while (adc2_link.available() > 0) {
        if (aim_framer_push(&g_adc2_framer, (uint8_t)adc2_link.read(), &f)) {
            handle(f);
        }
    }
}
