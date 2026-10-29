       >>source format free
identification division.
program-id. boreal-batch.
environment division.
input-output section.
file-control.
    select input-file assign to input-path
      organization line sequential file status input-status.
    select output-file assign to output-path
      organization line sequential file status output-status.
data division.
file section.
fd input-file.
01 input-line pic x(81).
fd output-file.
01 output-line pic x(256).
working-storage section.
01 input-path pic x(256).
01 output-path pic x(256).
01 input-status pic xx.
01 output-status pic xx.
01 policy-version pic xx.
01 done-flag pic 9 value 0.
   88 done value 1.
01 row-count binary-long value 0.
01 duplicate-flag pic x.
copy 'detail-v1.cpy'.
copy 'result-v1.cpy'.
01 display-payable pic 9(7).99.
01 display-unrounded pic 9(9).9999.
01 display-rounded pic 9(9).99.
01 display-rate pic 9.99.
procedure division.
    accept input-path from argument-value end-accept
    accept output-path from argument-value end-accept
    accept policy-version from argument-value end-accept
    open input input-file
    if input-status not = '00' perform io-failure end-if
    open output output-file
    if output-status not = '00' perform io-failure end-if
    perform until done
        read input-file end-read
        evaluate input-status
          when '10' set done to true
          when '00'
            add 1 to row-count end-add
            if row-count > 500
                move 65 to return-code goback
            end-if
            move input-line(1:80) to legacy-detail
            move input-line(81:1) to duplicate-flag
            call 'validate-record' using legacy-detail duplicate-flag
                calculation-result
            end-call
            call 'calculate-award' using policy-version
                calculation-result
            end-call
            call 'construct-journal' using calculation-result end-call
            move payable-award to display-payable
            move unrounded-award to display-unrounded
            move rounded-award to display-rounded
            move reimbursement-rate to display-rate
            move spaces to output-line
            string function trim(result-reason) '|' display-payable
                '|' display-unrounded '|' display-rounded '|'
                display-rate '|' debit-account '|' credit-account
                into output-line
            end-string
            write output-line end-write
            if output-status not = '00' perform io-failure end-if
          when other perform io-failure
        end-evaluate
    end-perform
    close input-file
    if input-status not = '00' perform io-failure end-if
    close output-file
    if output-status not = '00' perform io-failure end-if
    move 0 to return-code
    goback.
io-failure.
    display 'ENGINE_IO|' input-status '|' output-status upon syserr end-display
    move 74 to return-code
    stop run.
