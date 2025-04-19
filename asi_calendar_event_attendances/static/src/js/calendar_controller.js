/** @odoo-module **/

import { CalendarController } from "@web/views/calendar/calendar_controller"
import { patch } from "@web/core/utils/patch"
import { useService } from "@web/core/utils/hooks"

patch(CalendarController.prototype, "calendar_participation.CalendarController", {
  setup() {
    this._super(...arguments)
    this.rpc = useService("rpc")
    this.notification = useService("notification")
  },

  /**
   * Marca la participación del asistente
   *
   * @param {integer} attendeeId - ID del asistente
   */
  async markParticipation(attendeeId) {
    const result = await this.rpc("/calendar/participation/mark/" + attendeeId)

    if (result.success) {
      this.notification.add(this.env._t("Participación registrada correctamente"), { type: "success" })
      // Recargar la vista para reflejar los cambios
      await this.model.load()
    } else {
      this.notification.add(result.error || this.env._t("No se pudo registrar la participación"), { type: "danger" })
    }
  },
})

