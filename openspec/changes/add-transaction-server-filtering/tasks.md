## 1. Implementer (backend)
- [ ] 1.1 Add the query parameters and validation to `transactions/schemas.py` and `api.py`; `date_from > date_to` → 422 "Nieprawidłowy zakres dat"
- [ ] 1.2 Filter, sort (stable, `id` as second key) and page in `transactions/service.py`, always by `user_id`; return `{items, total}`

## 2. Implementer (frontend)
- [ ] 2.1 Send filters, sort and paging from `TransactionsPage.tsx` / `queries.ts`; replace the month picker with a date range
- [ ] 2.2 Add "Pokaż więcej" or pagination; adapt `list.ts` to `{items, total}`

## 3. Tester
- [ ] 3.1 Backend tests: every filter, sort order, page bounds (offset past the end → empty list), 422 on a reversed range
- [ ] 3.2 Isolation test: another user's transactions never appear in `items` or `total`
- [ ] 3.3 Update `list.test.ts`

## 4. Verify
- [ ] 4.1 `make lint`, `COFFER_TEST_DB=coffer_test_transactions make test-backend ARGS="tests/transactions"`, `make check-web`, `make openapi`
