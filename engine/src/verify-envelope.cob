       >>source format free
identification division.
program-id. boreal-envelope.
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
01 input-line pic x(80).
fd output-file.
01 output-line pic x(128).
working-storage section.
01 input-path pic x(256).
01 output-path pic x(256).
01 input-status pic xx.
01 output-status pic xx.
01 envelope-state pic x value 'H'.
   88 expecting-header value 'H'.
   88 expecting-detail value 'D'.
   88 after-trailer value 'T'.
01 done-flag pic 9 value 0.
   88 done value 1.
01 error-code pic x(32) value spaces.
01 detail-count pic 9(9) comp-3 value 0.
01 total-amount pic s9(13)v99 comp-3 value 0.
01 row-amount pic s9(7)v99 comp-3.
01 trailer-amount pic s9(13)v99 comp-3.
01 trailer-count pic 9(9) comp-3.
01 display-count pic 9(9).
01 display-total pic +9(13).99.
01 date-number binary-long.
copy 'detail-v1.cpy'.
procedure division.
    accept input-path from argument-value end-accept
    accept output-path from argument-value end-accept
    open input input-file
    if input-status not = '00' perform io-failure end-if
    perform until done
        read input-file end-read
        evaluate input-status
          when '10' set done to true
          when '00'
            if error-code = spaces perform verify-line end-if
          when other perform io-failure
        end-evaluate
    end-perform
    if error-code = spaces and not after-trailer
        move 'TRAILER_MISSING' to error-code
    end-if
    close input-file
    if input-status not = '00' perform io-failure end-if
    open output output-file
    if output-status not = '00' perform io-failure end-if
    move spaces to output-line
    if error-code = spaces
        move detail-count to display-count
        move total-amount to display-total
        string 'OK|' display-count '|' display-total into output-line
        end-string
    else
        string 'ERROR|' function trim(error-code) into output-line
        end-string
    end-if
    write output-line end-write
    if output-status not = '00' perform io-failure end-if
    close output-file
    if output-status not = '00' perform io-failure end-if
    move 0 to return-code
    goback.
verify-line.
    evaluate true
      when expecting-header
        if input-line(1:9) not = 'HBOREAL01'
          or input-line(10:24) = spaces
          or input-line(34:8) is not numeric
          or input-line(42:39) not = spaces
            move 'HEADER_INVALID' to error-code
        else
            move function numval(input-line(34:8)) to date-number
            if function test-date-yyyymmdd(date-number) not = 0
                move 'HEADER_INVALID' to error-code
            end-if
            move 'D' to envelope-state
        end-if
      when after-trailer
        move 'DATA_AFTER_TRAILER' to error-code
      when input-line(1:1) = 'D'
        move input-line to legacy-detail
        if (detail-amount(1:1) not = '+' and not = '-')
          or detail-amount(2:7) is not numeric
          or detail-amount(9:1) not = '.'
          or detail-amount(10:2) is not numeric
            move 'CONTROL_AMOUNT_SYNTAX' to error-code
        else
            compute row-amount = function numval(detail-amount)
              on size error move 'CONTROL_OVERFLOW' to error-code
            end-compute
            add row-amount to total-amount
              on size error move 'CONTROL_OVERFLOW' to error-code
            end-add
            add 1 to detail-count
              on size error move 'CONTROL_OVERFLOW' to error-code
            end-add
        end-if
      when input-line(1:1) = 'T'
        if input-line(2:9) is not numeric
          or (input-line(11:1) not = '+' and not = '-')
          or input-line(12:13) is not numeric
          or input-line(25:1) not = '.'
          or input-line(26:2) is not numeric
          or input-line(28:53) not = spaces
            move 'TRAILER_INVALID' to error-code
        else
            compute trailer-count = function numval(input-line(2:9))
              on size error move 'CONTROL_OVERFLOW' to error-code
            end-compute
            compute trailer-amount = function numval(input-line(11:17))
              on size error move 'CONTROL_OVERFLOW' to error-code
            end-compute
            if trailer-count not = detail-count
                move 'CONTROL_COUNT_MISMATCH' to error-code
            end-if
            if trailer-amount not = total-amount
                move 'CONTROL_TOTAL_MISMATCH' to error-code
            end-if
            if detail-count = 0 move 'EMPTY_BATCH' to error-code end-if
        end-if
        move 'T' to envelope-state
      when other
        move 'RECORD_TYPE_INVALID' to error-code
    end-evaluate.
io-failure.
    display 'ENGINE_IO|' input-status '|' output-status upon syserr end-display
    move 74 to return-code
    stop run.
