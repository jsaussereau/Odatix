proc is_slack_met {report_path timing_rep} {
  set tfile [open $timing_rep]
  while {[gets $tfile data] != -1} {
    if {[string match *Slack* $data]} {
     if {[regexp {[-]?[0-9]*\.?[0-9]+} $data match]} {
        if {$match >= 0} {
          close $tfile
          return 1
        }
      }
    }
  }
  close $tfile
  return 0
}


proc is_slack_inf {report_path timing_rep} {
  set tfile [open $timing_rep]
  while {[gets $tfile data] != -1} {
    if {[string match *[string toupper "Path is unconstrained"]* [string toupper $data]]} {
      close $tfile
      return 1
    }
    if {[string match *[string toupper "No paths."]* [string toupper $data]]} {
      close $tfile
      return 1
    }
  }
  close $tfile
  return 0
}