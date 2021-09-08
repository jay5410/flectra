# -*- coding: utf-8 -*-
# Part of Odoo, Flectra. See LICENSE file for full copyright and licensing details.

from flectra.addons.mrp.tests.common import TestMrpCommon
from flectra.tests import Form
from flectra.tests.common import SavepointCase


class TestMrpProductionBackorder(TestMrpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock_location = cls.env.ref('stock.stock_location_stock')

    def setUp(self):
        super().setUp()
        warehouse_form = Form(self.env['stock.warehouse'])
        warehouse_form.name = 'Test Warehouse'
        warehouse_form.code = 'TWH'
        self.warehouse = warehouse_form.save()

    def test_no_tracking_1(self):
        """Create a MO for 4 product. Produce 4. The backorder button should
        not appear and hitting mark as done should not open the backorder wizard.
        The name of the MO should be MO/001.
        """
        mo = self.generate_mo(qty_final=4)[0]

        mo_form = Form(mo)
        mo_form.qty_producing = 4
        mo = mo_form.save()

        # No backorder is proposed
        self.assertTrue(mo.button_mark_done())
        self.assertEqual(mo._get_quantity_to_backorder(), 0)
        self.assertTrue("-001" not in mo.name)

    def test_no_tracking_2(self):
        """Create a MO for 4 product. Produce 1. The backorder button should
        appear and hitting mark as done should open the backorder wizard. In the backorder
        wizard, choose to do the backorder. A new MO for 3 self.untracked_bom should be
        created.
        The sequence of the first MO should be MO/001-01, the sequence of the second MO
        should be MO/001-02.
        Check that all MO are reachable through the procurement group.
        """
        production, _, _, product_to_use_1, _ = self.generate_mo(qty_final=4, qty_base_1=3)
        self.assertEqual(production.state, 'confirmed')
        self.assertEqual(production.reserve_visible, True)

        # Make some stock and reserve
        for product in production.move_raw_ids.product_id:
            self.env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': product.id,
                'inventory_quantity': 100,
                'location_id': production.location_src_id.id,
            })
        production.action_assign()
        self.assertEqual(production.state, 'confirmed')
        self.assertEqual(production.reserve_visible, False)

        mo_form = Form(production)
        mo_form.qty_producing = 1
        production = mo_form.save()

        action = production.button_mark_done()
        backorder = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
        backorder.save().action_backorder()

        # Two related MO to the procurement group
        self.assertEqual(len(production.procurement_group_id.mrp_production_ids), 2)

        # Check MO backorder
        mo_backorder = production.procurement_group_id.mrp_production_ids[-1]
        self.assertEqual(mo_backorder.product_id.id, production.product_id.id)
        self.assertEqual(mo_backorder.product_qty, 3)
        self.assertEqual(sum(mo_backorder.move_raw_ids.filtered(lambda m: m.product_id.id == product_to_use_1.id).mapped("product_uom_qty")), 9)
        self.assertEqual(mo_backorder.reserve_visible, False)  # the reservation of the first MO should've been moved here

    def test_no_tracking_pbm_1(self):
        """Create a MO for 4 product. Produce 1. The backorder button should
        appear and hitting mark as done should open the backorder wizard. In the backorder
        wizard, choose to do the backorder. A new MO for 3 self.untracked_bom should be
        created.
        The sequence of the first MO should be MO/001-01, the sequence of the second MO
        should be MO/001-02.
        Check that all MO are reachable through the procurement group.
        """
        with Form(self.warehouse) as warehouse:
            warehouse.manufacture_steps = 'pbm'

        production, _, product_to_build, product_to_use_1, product_to_use_2 = self.generate_mo(qty_base_1=4, qty_final=4, picking_type_id=self.warehouse.manu_type_id)

        move_raw_ids = production.move_raw_ids
        self.assertEqual(len(move_raw_ids), 2)
        self.assertEqual(set(move_raw_ids.mapped("product_id")), {product_to_use_1, product_to_use_2})

        pbm_move = move_raw_ids.move_orig_ids
        self.assertEqual(len(pbm_move), 2)
        self.assertEqual(set(pbm_move.mapped("product_id")), {product_to_use_1, product_to_use_2})
        self.assertFalse(pbm_move.move_orig_ids)

        mo_form = Form(production)
        mo_form.qty_producing = 1
        production = mo_form.save()
        self.assertEqual(sum(pbm_move.filtered(lambda m: m.product_id.id == product_to_use_1.id).mapped("product_qty")), 16)
        self.assertEqual(sum(pbm_move.filtered(lambda m: m.product_id.id == product_to_use_2.id).mapped("product_qty")), 4)

        action = production.button_mark_done()
        backorder = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
        backorder.save().action_backorder()

        mo_backorder = production.procurement_group_id.mrp_production_ids[-1]
        self.assertEqual(mo_backorder.delivery_count, 1)

        pbm_move |= mo_backorder.move_raw_ids.move_orig_ids
        # Check that quantity is correct
        self.assertEqual(sum(pbm_move.filtered(lambda m: m.product_id.id == product_to_use_1.id).mapped("product_qty")), 16)
        self.assertEqual(sum(pbm_move.filtered(lambda m: m.product_id.id == product_to_use_2.id).mapped("product_qty")), 4)

        self.assertFalse(pbm_move.move_orig_ids)

    def test_no_tracking_pbm_sam_1(self):
        """Create a MO for 4 product. Produce 1. The backorder button should
        appear and hitting mark as done should open the backorder wizard. In the backorder
        wizard, choose to do the backorder. A new MO for 3 self.untracked_bom should be
        created.
        The sequence of the first MO should be MO/001-01, the sequence of the second MO
        should be MO/001-02.
        Check that all MO are reachable through the procurement group.
        """
        with Form(self.warehouse) as warehouse:
            warehouse.manufacture_steps = 'pbm_sam'
        production, _, product_to_build, product_to_use_1, product_to_use_2 = self.generate_mo(qty_base_1=4, qty_final=4, picking_type_id=self.warehouse.manu_type_id)

        move_raw_ids = production.move_raw_ids
        self.assertEqual(len(move_raw_ids), 2)
        self.assertEqual(set(move_raw_ids.mapped("product_id")), {product_to_use_1, product_to_use_2})

        pbm_move = move_raw_ids.move_orig_ids
        self.assertEqual(len(pbm_move), 2)
        self.assertEqual(set(pbm_move.mapped("product_id")), {product_to_use_1, product_to_use_2})
        self.assertFalse(pbm_move.move_orig_ids)
        self.assertEqual(sum(pbm_move.filtered(lambda m: m.product_id.id == product_to_use_1.id).mapped("product_qty")), 16)
        self.assertEqual(sum(pbm_move.filtered(lambda m: m.product_id.id == product_to_use_2.id).mapped("product_qty")), 4)

        sam_move = production.move_finished_ids.move_dest_ids
        self.assertEqual(len(sam_move), 1)
        self.assertEqual(sam_move.product_id.id, product_to_build.id)
        self.assertEqual(sum(sam_move.mapped("product_qty")), 4)

        mo_form = Form(production)
        mo_form.qty_producing = 1
        production = mo_form.save()

        action = production.button_mark_done()
        backorder = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
        backorder.save().action_backorder()

        mo_backorder = production.procurement_group_id.mrp_production_ids[-1]
        self.assertEqual(mo_backorder.delivery_count, 2)

        pbm_move |= mo_backorder.move_raw_ids.move_orig_ids
        self.assertEqual(sum(pbm_move.filtered(lambda m: m.product_id.id == product_to_use_1.id).mapped("product_qty")), 16)
        self.assertEqual(sum(pbm_move.filtered(lambda m: m.product_id.id == product_to_use_2.id).mapped("product_qty")), 4)

        sam_move |= mo_backorder.move_finished_ids.move_orig_ids
        self.assertEqual(sum(sam_move.mapped("product_qty")), 4)

    def test_tracking_backorder_series_lot_1(self):
        """ Create a MO of 4 tracked products. all component is tracked by lots
        Produce one by one with one bakorder for each until end.
        """
        nb_product_todo = 4
        production, _, p_final, p1, p2 = self.generate_mo(qty_final=nb_product_todo, tracking_final='lot', tracking_base_1='lot', tracking_base_2='lot')
        lot_final = self.env['stock.production.lot'].create({
            'name': 'lot_final',
            'product_id': p_final.id,
            'company_id': self.env.company.id,
        })
        lot_1 = self.env['stock.production.lot'].create({
            'name': 'lot_consumed_1',
            'product_id': p1.id,
            'company_id': self.env.company.id,
        })
        lot_2 = self.env['stock.production.lot'].create({
            'name': 'lot_consumed_2',
            'product_id': p2.id,
            'company_id': self.env.company.id,
        })

        self.env['stock.quant']._update_available_quantity(p1, self.stock_location, nb_product_todo*4, lot_id=lot_1)
        self.env['stock.quant']._update_available_quantity(p2, self.stock_location, nb_product_todo, lot_id=lot_2)

        production.action_assign()
        active_production = production
        for i in range(nb_product_todo):

            details_operation_form = Form(active_production.move_raw_ids.filtered(lambda m: m.product_id == p1), view=self.env.ref('stock.view_stock_move_operations'))
            with details_operation_form.move_line_ids.edit(0) as ml:
                ml.qty_done = 4
                ml.lot_id = lot_1
            details_operation_form.save()
            details_operation_form = Form(active_production.move_raw_ids.filtered(lambda m: m.product_id == p2), view=self.env.ref('stock.view_stock_move_operations'))
            with details_operation_form.move_line_ids.edit(0) as ml:
                ml.qty_done = 1
                ml.lot_id = lot_2
            details_operation_form.save()

            production_form = Form(active_production)
            production_form.qty_producing = 1
            production_form.lot_producing_id = lot_final
            active_production = production_form.save()

            active_production.button_mark_done()
            if i + 1 != nb_product_todo:  # If last MO, don't make a backorder
                action = active_production.button_mark_done()
                backorder = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
                backorder.save().action_backorder()
            active_production = active_production.procurement_group_id.mrp_production_ids[-1]

        self.assertEqual(self.env['stock.quant']._get_available_quantity(p_final, self.stock_location, lot_id=lot_final), nb_product_todo, f'You should have the {nb_product_todo} final product in stock')
        self.assertEqual(len(production.procurement_group_id.mrp_production_ids), nb_product_todo)

    def test_tracking_backorder_series_serial_1(self):
        """ Create a MO of 4 tracked products (serial) with pbm_sam.
        all component is tracked by serial
        Produce one by one with one bakorder for each until end.
        """
        nb_product_todo = 4
        production, _, p_final, p1, p2 = self.generate_mo(qty_final=nb_product_todo, tracking_final='serial', tracking_base_1='serial', tracking_base_2='serial', qty_base_1=1)
        serials_final, serials_p1, serials_p2 = [], [], []
        for i in range(nb_product_todo):
            serials_final.append(self.env['stock.production.lot'].create({
                'name': f'lot_final_{i}',
                'product_id': p_final.id,
                'company_id': self.env.company.id,
            }))
            serials_p1.append(self.env['stock.production.lot'].create({
                'name': f'lot_consumed_1_{i}',
                'product_id': p1.id,
                'company_id': self.env.company.id,
            }))
            serials_p2.append(self.env['stock.production.lot'].create({
                'name': f'lot_consumed_2_{i}',
                'product_id': p2.id,
                'company_id': self.env.company.id,
            }))
            self.env['stock.quant']._update_available_quantity(p1, self.stock_location, 1, lot_id=serials_p1[-1])
            self.env['stock.quant']._update_available_quantity(p2, self.stock_location, 1, lot_id=serials_p2[-1])

        production.action_assign()
        active_production = production
        for i in range(nb_product_todo):

            details_operation_form = Form(active_production.move_raw_ids.filtered(lambda m: m.product_id == p1), view=self.env.ref('stock.view_stock_move_operations'))
            with details_operation_form.move_line_ids.edit(0) as ml:
                ml.qty_done = 1
                ml.lot_id = serials_p1[i]
            details_operation_form.save()
            details_operation_form = Form(active_production.move_raw_ids.filtered(lambda m: m.product_id == p2), view=self.env.ref('stock.view_stock_move_operations'))
            with details_operation_form.move_line_ids.edit(0) as ml:
                ml.qty_done = 1
                ml.lot_id = serials_p2[i]
            details_operation_form.save()

            production_form = Form(active_production)
            production_form.qty_producing = 1
            production_form.lot_producing_id = serials_final[i]
            active_production = production_form.save()

            active_production.button_mark_done()
            if i + 1 != nb_product_todo:  # If last MO, don't make a backorder
                action = active_production.button_mark_done()
                backorder = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
                backorder.save().action_backorder()
            active_production = active_production.procurement_group_id.mrp_production_ids[-1]

        self.assertEqual(self.env['stock.quant']._get_available_quantity(p_final, self.stock_location), nb_product_todo, f'You should have the {nb_product_todo} final product in stock')
        self.assertEqual(len(production.procurement_group_id.mrp_production_ids), nb_product_todo)

    def test_backorder_name(self):
        def produce_one(mo):
            mo_form = Form(mo)
            mo_form.qty_producing = 1
            mo = mo_form.save()
            action = mo.button_mark_done()
            backorder = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
            backorder.save().action_backorder()
            return mo.procurement_group_id.mrp_production_ids[-1]

        default_picking_type_id = self.env['mrp.production']._get_default_picking_type()
        default_picking_type = self.env['stock.picking.type'].browse(default_picking_type_id)
        mo_sequence = default_picking_type.sequence_id

        mo_sequence.prefix = "WH-MO-"
        initial_mo_name = mo_sequence.prefix + str(mo_sequence.number_next_actual).zfill(mo_sequence.padding)

        production = self.generate_mo(qty_final=5)[0]
        self.assertEqual(production.name, initial_mo_name)

        backorder = produce_one(production)
        self.assertEqual(production.name, initial_mo_name + "-001")
        self.assertEqual(backorder.name, initial_mo_name + "-002")

        backorder.backorder_sequence = 998

        for seq in [998, 999, 1000]:
            new_backorder = produce_one(backorder)
            self.assertEqual(backorder.name, initial_mo_name + "-" + str(seq))
            self.assertEqual(new_backorder.name, initial_mo_name + "-" + str(seq + 1))
            backorder = new_backorder

    def test_backorder_name_without_procurement_group(self):
        production = self.generate_mo(qty_final=5)[0]
        mo_form = Form(production)
        mo_form.qty_producing = 1
        mo = mo_form.save()

        # Remove pg to trigger fallback on backorder name
        mo.procurement_group_id = False
        action = mo.button_mark_done()
        backorder_form = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
        backorder_form.save().action_backorder()

        # The pg is back
        self.assertTrue(production.procurement_group_id)
        backorder_ids = production.procurement_group_id.mrp_production_ids[1]
        self.assertEqual(production.name.split('-')[0], backorder_ids.name.split('-')[0])
        self.assertEqual(int(production.name.split('-')[1]) + 1, int(backorder_ids.name.split('-')[1]))


class TestMrpWorkorderBackorder(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super(TestMrpWorkorderBackorder, cls).setUpClass()
        cls.uom_unit = cls.env['uom.uom'].search([
            ('category_id', '=', cls.env.ref('uom.product_uom_categ_unit').id),
            ('uom_type', '=', 'reference')
        ], limit=1)
        cls.finished1 = cls.env['product.product'].create({
            'name': 'finished1',
            'type': 'product',
        })
        cls.compfinished1 = cls.env['product.product'].create({
            'name': 'compfinished1',
            'type': 'product',
        })
        cls.compfinished2 = cls.env['product.product'].create({
            'name': 'compfinished2',
            'type': 'product',
        })
        cls.workcenter1 = cls.env['mrp.workcenter'].create({
            'name': 'workcenter1',
        })
        cls.workcenter2 = cls.env['mrp.workcenter'].create({
            'name': 'workcenter2',
        })

        cls.bom_finished1 = cls.env['mrp.bom'].create({
            'product_id': cls.finished1.id,
            'product_tmpl_id': cls.finished1.product_tmpl_id.id,
            'product_uom_id': cls.uom_unit.id,
            'product_qty': 1,
            'consumption': 'flexible',
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {'product_id': cls.compfinished1.id, 'product_qty': 1}),
                (0, 0, {'product_id': cls.compfinished2.id, 'product_qty': 1}),
            ],
            'operation_ids': [
                (0, 0, {'sequence': 1, 'name': 'finished operation 1', 'workcenter_id': cls.workcenter1.id}),
                (0, 0, {'sequence': 2, 'name': 'finished operation 2', 'workcenter_id': cls.workcenter2.id}),
            ],
        })
        cls.bom_finished1.bom_line_ids[0].operation_id = cls.bom_finished1.operation_ids[0].id
        cls.bom_finished1.bom_line_ids[1].operation_id = cls.bom_finished1.operation_ids[1].id
