       >>source format free
identification division.
program-id. calculate-award.
data division.
linkage section.
01 policy-version pic xx.
copy 'result-v1.cpy'.
procedure division using policy-version calculation-result.
    if not result-accepted goback end-if
    evaluate policy-version
      when 'V1' move 0.75 to reimbursement-rate
      when 'V2' move 0.80 to reimbursement-rate
      when other
        move 'POLICY_UNSUPPORTED' to result-reason
        goback
    end-evaluate
    compute unrounded-award = eligible-cost * reimbursement-rate
      on size error move 'AMOUNT_OVERFLOW' to result-reason
    end-compute
    if not result-accepted goback end-if
    compute rounded-award rounded = unrounded-award
      on size error move 'AMOUNT_OVERFLOW' to result-reason
    end-compute
    if not result-accepted goback end-if
    compute payable-award = function min(2500.00, rounded-award)
      on size error move 'AMOUNT_OVERFLOW' to result-reason
    end-compute
    goback.
end program calculate-award.
