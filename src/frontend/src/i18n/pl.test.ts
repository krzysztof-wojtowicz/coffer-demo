import { expect, test } from 'vitest'
import { pl } from './pl'

test('pl contains appName', () => {
  expect(pl).toHaveProperty('appName')
})
