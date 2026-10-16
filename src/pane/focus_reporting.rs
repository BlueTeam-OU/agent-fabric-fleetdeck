/// Sees each DECSET that names focus reporting (`CSI ? … 1004 … h`) in PTY
/// output, split across reads or not, following the terminal's parser
/// through escape and CSI sequences. It does not model the other states: a
/// C1 CSI that breaks into a string or a DCS header (`ESC _ … 0x9B ? 1004 h`)
/// goes unseen. No real program writes one, and a set missed while the mode
/// is on costs only the answer, never a wrong one.
///
/// The terminal core keeps only the mode's current value, so a set while it
/// is already on (a program starting after one that left it on) is invisible
/// there. Ghostty's own app layer answers each such set with the current
/// focus, and a program that turns it on may wait for that answer before it
/// counts itself focused; this tracker is how herdr sees the same sets.
#[derive(Debug, Default)]
pub(crate) struct FocusReportingSetTracker {
    state: ParseState,
    seen: bool,
}

#[derive(Debug, Default)]
enum ParseState {
    #[default]
    Ground,
    Escape,
    CsiStart,
    Private {
        param: Option<u16>,
        names_focus: bool,
    },
    /// A CSI that is not a DEC private mode set, read to its final byte.
    Other,
}

const FOCUS_REPORTING_MODE: u16 = 1004;

impl FocusReportingSetTracker {
    pub(crate) fn observe(&mut self, mut bytes: &[u8]) {
        while !bytes.is_empty() {
            if matches!(self.state, ParseState::Ground) {
                let Some(escape) = bytes.iter().position(|&byte| byte == 0x1b) else {
                    return;
                };
                bytes = &bytes[escape..];
            }
            self.observe_byte(bytes[0]);
            bytes = &bytes[1..];
        }
    }

    /// Whether a set was seen since the last call.
    pub(crate) fn take_seen(&mut self) -> bool {
        std::mem::take(&mut self.seen)
    }

    fn observe_byte(&mut self, byte: u8) {
        if byte == 0x1b {
            self.state = ParseState::Escape;
            return;
        }
        if !matches!(self.state, ParseState::Ground) {
            if passes_through_sequence(byte) {
                return;
            }
            if byte == C1_CSI {
                self.state = ParseState::CsiStart;
                return;
            }
        }
        match &mut self.state {
            ParseState::Ground => {}
            ParseState::Escape => {
                self.state = if byte == b'[' {
                    ParseState::CsiStart
                } else {
                    ParseState::Ground
                };
            }
            ParseState::CsiStart if byte == b'?' => {
                self.state = ParseState::Private {
                    param: None,
                    names_focus: false,
                };
            }
            ParseState::CsiStart => {
                self.state = ParseState::Other;
                self.observe_other(byte);
            }
            ParseState::Private { param, names_focus } => {
                if byte.is_ascii_digit() {
                    let digit = u16::from(byte - b'0');
                    *param = Some(param.unwrap_or(0).saturating_mul(10).saturating_add(digit));
                } else if byte == b';' {
                    *names_focus |= *param == Some(FOCUS_REPORTING_MODE);
                    *param = None;
                } else if byte == b'h' {
                    if *names_focus || *param == Some(FOCUS_REPORTING_MODE) {
                        self.seen = true;
                    }
                    self.state = ParseState::Ground;
                } else if (0x40..=0x7e).contains(&byte) || !(0x20..=0x3f).contains(&byte) {
                    // Another final byte (a reset, a query) or a byte no CSI
                    // carries: not a set.
                    self.state = ParseState::Ground;
                } else {
                    // An intermediate or a sub-parameter makes it some other
                    // sequence; read it to its end.
                    self.state = ParseState::Other;
                }
            }
            ParseState::Other => self.observe_other(byte),
        }
    }

    fn observe_other(&mut self, byte: u8) {
        if (0x40..=0x7e).contains(&byte) || !(0x20..=0x3f).contains(&byte) {
            self.state = ParseState::Ground;
        }
    }
}

/// A byte the terminal's parser lets a sequence go on around (Ghostty's
/// parse_table.zig, as in the VT500 parser it follows): a C0 control it
/// executes there, DEL, or a byte from 0xA0 up, which it ignores. CAN, SUB
/// and the other C1 bytes cancel the sequence instead, and C1_CSI starts a
/// new one. Inside a sequence the parser sees raw bytes; only in ground are
/// they decoded as UTF-8 first, so there a 0x9B is text, not a CSI.
fn passes_through_sequence(byte: u8) -> bool {
    matches!(byte, 0x00..=0x17 | 0x19 | 0x1c..=0x1f | 0x7f | 0xa0..=0xff)
}

const C1_CSI: u8 = 0x9b;

#[cfg(test)]
mod tests {
    use super::FocusReportingSetTracker;

    fn seen(chunks: &[&[u8]]) -> bool {
        let mut tracker = FocusReportingSetTracker::default();
        let mut seen = false;
        for chunk in chunks {
            tracker.observe(chunk);
            seen |= tracker.take_seen();
        }
        seen
    }

    #[test]
    fn sees_a_set_alone_or_among_other_modes() {
        assert!(seen(&[b"\x1b[?1004h"]));
        assert!(seen(&[b"text\x1b[?2004;1004;1006h more"]));
        assert!(seen(&[b"\x1b[?1004;2004h"]));
    }

    #[test]
    fn sees_a_set_split_across_reads() {
        assert!(seen(&[b"\x1b", b"[?10", b"04", b"h"]));
        assert!(seen(&[b"\x1b[?2004;", b"1004h"]));
    }

    #[test]
    fn ignores_resets_queries_and_other_modes() {
        assert!(!seen(&[b"\x1b[?1004l"]));
        assert!(!seen(&[b"\x1b[?1004$p"]));
        assert!(!seen(&[b"\x1b[?10040h\x1b[?100h\x1b[?2004h"]));
        assert!(!seen(&[b"\x1b[1004h"]));
        assert!(!seen(&[b"1004h \x1b[>1004h"]));
    }

    #[test]
    fn an_escape_inside_a_sequence_starts_a_new_one() {
        assert!(seen(&[b"\x1b[?20\x1b[?1004h"]));
        assert!(!seen(&[b"\x1b[?1004\x1b[?2004h"]));
    }

    #[test]
    fn a_control_inside_a_sequence_leaves_it_going() {
        assert!(seen(&[b"\x1b[?10\r04h"]));
        assert!(seen(&[b"\x1b\n[?1004\x7fh"]));
        assert!(seen(&[b"\x1b[\x08?1004;\x00h"]));
        assert!(!seen(&[b"\x1b[?1004\x18h"]), "CAN cancels it");
        assert!(!seen(&[b"\x1b[?1004\x1ah"]), "so does SUB");
    }

    #[test]
    fn a_high_byte_inside_a_sequence_leaves_it_going_or_starts_another() {
        assert!(seen(&[b"\x1b[?10\xa004h"]));
        assert!(seen(&[b"\x1b[?10\xc3\xa904h"]));
        assert!(seen(&[b"\x1b[?1\x9b?1004h"]), "a C1 CSI starts a new one");
        assert!(!seen(&[b"\x1b[?10\x8504h"]), "another C1 byte cancels it");
        assert!(!seen(&[b"\x9b?1004h"]), "text outside a sequence");
    }

    #[test]
    fn take_seen_reports_each_set_once() {
        let mut tracker = FocusReportingSetTracker::default();
        tracker.observe(b"\x1b[?1004h");
        assert!(tracker.take_seen());
        tracker.observe(b"plain output");
        assert!(!tracker.take_seen());
    }
}
