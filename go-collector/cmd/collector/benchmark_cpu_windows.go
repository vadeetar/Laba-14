//go:build windows

package main

import "golang.org/x/sys/windows"

func cpuTimeSeconds() float64 {
	var creation, exit, kernel, user windows.Filetime
	handle := windows.CurrentProcess()
	if err := windows.GetProcessTimes(handle, &creation, &exit, &kernel, &user); err != nil {
		return 0
	}
	return float64(kernel.Nanoseconds()+user.Nanoseconds()) / 1e9
}
