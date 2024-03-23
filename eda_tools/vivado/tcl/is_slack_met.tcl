proc is_slack_met {timing_rep} {
  set tfile [open $timing_rep]
  #check if we can find "slack (MET)" in the timing report
  while {[gets $tfile data] != -1} {
    if {[string match *[string toupper "slack (MET)"]* [string toupper $data]]} {
      close $tfile
      return 1  
    }
  }
  close $tfile
  return 0
}

proc is_slack_inf {timing_rep} {
  set tfile [open $timing_rep]
  #check if we can find "Slack:                    inf" in the timing report
  while {[gets $tfile data] != -1} {
    if {[string match *[string toupper "Slack:                    inf"]* [string toupper $data]]} {
      close $tfile
      return 1  
    }
  }
  close $tfile
  return 0
}
