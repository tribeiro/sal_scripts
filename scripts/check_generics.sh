#!/usr/bin/env bash

cmd="abort enable disable standby exitControl start enterControl setValue"

events="detailedState settingVersions errorCode summaryState appliedSettingsMatchStart"

echo
echo "== Checking commands =="
echo
for c in $cmd; do
    cat $1/$1_Commands.xml | grep $c
done

echo 
echo "== Checking events =="
echo

for c in $events; do
    cat $1/$1_Events.xml | grep logevent_$c
done

echo

