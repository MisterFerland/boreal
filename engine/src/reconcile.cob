       >>source format free
identification division.
program-id. boreal-reconcile.
environment division.
input-output section.
file-control.
    select input-file assign to input-path
      organization line sequential file status input-status.
    select output-file assign to output-path
      organization line sequential file status output-status.
    select sort-file assign to 'sort-work'.
data division.
file section.
fd input-file.
copy 'reconciliation-v1.cpy'.
fd output-file.
01 output-line pic x(128).
sd sort-file.
01 sort-row.
    05 sort-index pic 9(9).
    05 sort-key pic x(48).
    05 sort-body pic x(25).
working-storage section.
01 input-path pic x(256).
01 output-path pic x(256).
01 input-status pic xx.
01 output-status pic xx.
01 done-flag pic 9 value 0.
   88 done value 1.
01 expected-amount pic s9(7)v99 comp-3.
01 received-amount pic s9(7)v99 comp-3.
01 match-class pic x(20).
01 debit-account pic x(4).
01 credit-account pic x(4).
01 display-amount pic 9(7).99.
procedure division.
    accept input-path from argument-value end-accept
    accept output-path from argument-value end-accept
    sort sort-file on ascending key sort-key sort-index
      input procedure load-records
      output procedure classify-records
    if sort-return not = 0 perform io-failure end-if
    move 0 to return-code
    goback.
load-records.
    open input input-file
    if input-status not = '00' perform io-failure end-if
    perform until done
        read input-file end-read
        evaluate input-status
          when '10' set done to true
          when '00'
            move reconciliation-input to sort-row
            release sort-row
          when other perform io-failure
        end-evaluate
    end-perform
    close input-file
    if input-status not = '00' perform io-failure end-if.
classify-records.
    move 0 to done-flag
    open output output-file
    if output-status not = '00' perform io-failure end-if
    perform until done
        return sort-file
          at end set done to true
          not at end
            move sort-row to reconciliation-input
            perform classify-one
        end-return
    end-perform
    close output-file
    if output-status not = '00' perform io-failure end-if.
classify-one.
    if (expected-present not = 'Y' and not = 'N')
      or (received-present not = 'Y' and not = 'N')
      or (duplicate-indicator not = 'Y' and not = 'N')
        move 65 to return-code stop run
    end-if
    if expected-present = 'Y'
        if (expected-text(1:1) not = '+' and not = '-')
          or expected-text(2:7) is not numeric
          or expected-text(9:1) not = '.'
          or expected-text(10:2) is not numeric
            move 65 to return-code stop run
        end-if
        compute expected-amount = function numval(expected-text)
          on size error move 65 to return-code stop run
        end-compute
    end-if
    if received-present = 'Y'
        if (received-text(1:1) not = '+' and not = '-')
          or received-text(2:7) is not numeric
          or received-text(9:1) not = '.'
          or received-text(10:2) is not numeric
            move 65 to return-code stop run
        end-if
        compute received-amount = function numval(received-text)
          on size error move 65 to return-code stop run
        end-compute
    end-if
    move spaces to debit-account credit-account
    move zero to display-amount
    evaluate true
      when duplicate-indicator = 'Y'
        move 'DUPLICATE' to match-class
      when expected-present = 'N'
        move 'UNEXPECTED' to match-class
      when received-present = 'N'
        move 'MISSING' to match-class
      when expected-amount not = received-amount
        move 'AMOUNT_MISMATCH' to match-class
      when expected-amount <= 0
        move 'AMOUNT_MISMATCH' to match-class
      when other
        move 'MATCH' to match-class
        move '2100' to debit-account
        move '1100' to credit-account
        move expected-amount to display-amount
    end-evaluate
    move spaces to output-line
    string reconciliation-index '|' function trim(match-class) '|'
      debit-account '|' credit-account '|' display-amount
      into output-line
    end-string
    write output-line end-write
    if output-status not = '00' perform io-failure end-if.
io-failure.
    display 'ENGINE_IO|' input-status '|' output-status upon syserr end-display
    move 74 to return-code
    stop run.
