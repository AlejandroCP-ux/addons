/** @odoo-module **/

import { CalendarRenderer } from "@web/views/calendar/calendar_renderer"
import { patch } from "@web/core/utils/patch"

patch(CalendarRenderer.prototype, "calendar_participation.CalendarRenderer", {
  /**
   * Extiende el método para añadir indicadores de participación
   */
  getEventContent(info) {
    const result = this._super(...arguments)

    // Añadir indicador de participación
    if (info.event.extendedProps.isOngoing) {
      // Evento en curso
      const ongoingBadge = document.createElement("span")
      ongoingBadge.className = "o_calendar_ongoing_badge"
      ongoingBadge.innerHTML = `<i class="fa fa-clock-o"></i>`
      ongoingBadge.title = "Evento en curso"
      result.appendChild(ongoingBadge)
    }

    if (info.event.extendedProps.participationCount > 0) {
      // Evento con participación
      const participationBadge = document.createElement("span")
      participationBadge.className = "o_calendar_participation_badge"
      participationBadge.innerHTML = `<i class="fa fa-users"></i> ${info.event.extendedProps.participationCount}`
      participationBadge.title = `${info.event.extendedProps.participationCount} participantes (${Math.round(info.event.extendedProps.participationPercentage)}%)`
      result.appendChild(participationBadge)
    }

    return result
  },

  /**
   * Añade manejadores de eventos para los botones de participación
   */
  onAttached() {
    this._super(...arguments)

    // Añadir manejadores después de que el DOM se actualice
    setTimeout(() => {
      const participationButtons = document.querySelectorAll(".o_calendar_participation_button")
      participationButtons.forEach((button) => {
        button.addEventListener("click", (ev) => {
          const attendeeId = ev.currentTarget.dataset.attendeeId
          this.env.calendarController.markParticipation(attendeeId)
        })
      })
    }, 0)
  },
})

