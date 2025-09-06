# Trackly v2 Test Plan

This document outlines the test plan for Trackly v2.

## Phase 1: The Expense Form (MVP)

### Test Cases

| Test Case ID | Description | Steps | Expected Result |
|---|---|---|---|
| TC-001 | Submit expense form with valid data | 1. Navigate to the /expense page.<br>2. Fill out all fields with valid data.<br>3. Click "Log Expense". | The expense is logged to the Google Sheet with the correct data. |
| TC-002 | Submit expense form with missing required fields | 1. Navigate to the /expense page.<br>2. Leave the "Amount" field blank.<br>3. Click "Log Expense". | An error message is displayed to the user. |
| TC-003 | Submit expense form with invalid data | 1. Navigate to the /expense page.<br>2. Enter a non-numeric value in the "Amount" field.<br>3. Click "Log Expense". | An error message is displayed to the user. |
| TC-004 | Submit expense form with a single invoice | 1. Navigate to the /expense page.<br>2. Fill out all fields with valid data.<br>3. Attach a single invoice file.<br>4. Click "Log Expense". | The expense is logged to the Google Sheet, and the invoice is uploaded to Dropbox. |
| TC-005 | Submit expense form with multiple invoices | 1. Navigate to the /expense page.<br>2. Fill out all fields with valid data.<br>3. Attach multiple invoice files.<br>4. Click "Log Expense". | The expense is logged to the Google Sheet, and all invoices are uploaded to Dropbox. |
