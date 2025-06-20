/** @odoo-module **/

import { CalendarModel } from "@web/views/calendar/calendar_model"
import { patch } from "@web/core/utils/patch"

patch(CalendarModel.prototype, "calendar_participation.CalendarModel", {
  /**
   * Extiende el método para incluir información de participación
   */
  _recordToCalendarEvent(record) {
    const result = this._super(...arguments)

    // Añadir información de participación
    result.isOngoing = record.is_ongoing
    result.participationCount = record.participation_count
    result.participationPercentage = record.participation_percentage

    return result
  },
})

