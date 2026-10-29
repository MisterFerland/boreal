       >>source format free
identification division.
program-id. boreal-aggregate.
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
01 input-line pic x(11).
fd output-file.
01 output-line pic x(32).
working-storage section.
01 input-path pic x(256).
01 output-path pic x(256).
01 input-status pic xx.
01 output-status pic xx.
01 done-flag pic 9 value 0.
   88 done value 1.
01 amount-value pic s9(7)v99 comp-3.
01 total-value pic s9(13)v99 comp-3 value 0.
01 display-total pic +9(13).99.
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
            if (input-line(1:1) not = '+' and not = '-')
              or input-line(2:7) is not numeric
              or input-line(9:1) not = '.'
              or input-line(10:2) is not numeric
                move 65 to return-code stop run
            end-if
            compute amount-value = function numval(input-line)
              on size error move 65 to return-code stop run
            end-compute
            add amount-value to total-value
              on size error move 65 to return-code stop run
            end-add
          when other perform io-failure
        end-evaluate
    end-perform
    close input-file
    if input-status not = '00' perform io-failure end-if
    open output output-file
    if output-status not = '00' perform io-failure end-if
    move total-value to display-total
    move display-total to output-line
    write output-line end-write
    if output-status not = '00' perform io-failure end-if
    close output-file
    if output-status not = '00' perform io-failure end-if
    move 0 to return-code
    goback.
io-failure.
    display 'ENGINE_IO|' input-status '|' output-status upon syserr
    end-display
    move 74 to return-code
    stop run.
