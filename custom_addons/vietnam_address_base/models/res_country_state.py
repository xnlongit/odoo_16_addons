import re
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class CountryState(models.Model):
    _inherit = 'res.country.state'
    _order = 'code_ext'

    def _make_code_ext(self):
        for record in self:
            if not record.code_ext:
                record.code_ext = record.code

    code_ext = fields.Char(string='State Code', required=True, compute=_make_code_ext, store=True)
    ward_ids = fields.One2many('res.country.ward', 'state_id')
    is_vietnam_new_province = fields.Boolean(
        string='Is Vietnam New Province',
        default=False,
        help='Đánh dấu tỉnh thành thuộc danh sách 34 tỉnh thành mới theo Nghị quyết 202/2025/QH15'
    )
    active = fields.Boolean(default=True)
    old_province_mapping = fields.Text(
        string='Old Province Mapping',
        help='Mapping từ tỉnh thành cũ sang tỉnh thành mới'
    )

    @api.model
    def _get_vietnam_country_id(self):
        return self.env.ref('base.vn').id

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        args += [('country_id', '=', self._get_vietnam_country_id())]
        return super().name_search(name, args, operator, limit)

    @api.model
    def migrate_old_provinces(self):
        """Migrate old provinces to new provinces"""
        _logger.info("Starting migration of old Vietnam provinces to new provinces")

        vietnam_country_id = self._get_vietnam_country_id()
        if not vietnam_country_id:
            _logger.error("Vietnam country not found")
            return False

        # Migration mapping - old province codes to new province codes
        # Theo bảng 23 đơn vị hành chính mới được hình thành từ việc hợp nhất
        migration_mapping = {
            # 1. Tuyên Quang + Hà Giang → Tuyên Quang
            'VN-03': 'VN-07',  # Hà Giang → Tuyên Quang

            # 2. Lào Cai + Yên Bái → Lào Cai (trung tâm Yên Bái)
            'VN-06': 'VN-02',  # Yên Bái → Lào Cai

            # 3. Thái Nguyên + Bắc Kạn → Thái Nguyên
            'VN-53': 'VN-69',  # Bắc Kạn → Thái Nguyên

            # 4. Phú Thọ + Vĩnh Phúc + Hòa Bình → Phú Thọ
            'VN-70': 'VN-68',  # Vĩnh Phúc → Phú Thọ
            'VN-14': 'VN-68',  # Hòa Bình → Phú Thọ

            # 5. Bắc Ninh + Bắc Giang → Bắc Ninh (trung tâm Bắc Giang)
            'VN-54': 'VN-56',  # Bắc Giang → Bắc Ninh

            # 6. Hưng Yên + Thái Bình → Hưng Yên
            'VN-20': 'VN-66',  # Thái Bình → Hưng Yên

            # 7. Hải Phòng + Hải Dương → Hải Phòng
            'VN-61': 'VN-HP',  # Hải Dương → Hải Phòng

            # 8. Ninh Bình + Hà Nam + Nam Định → Ninh Bình
            'VN-63': 'VN-18',  # Hà Nam → Ninh Bình
            'VN-67': 'VN-18',  # Nam Định → Ninh Bình

            # 9. Quảng Trị + Quảng Bình → Quảng Trị (trung tâm Quảng Bình)
            'VN-24': 'VN-25',  # Quảng Bình → Quảng Trị

            # 10. Đà Nẵng + Quảng Nam → Đà Nẵng
            'VN-27': 'VN-DN',  # Quảng Nam → Đà Nẵng

            # 11. Quảng Ngãi + Kon Tum → Quảng Ngãi
            'VN-28': 'VN-29',  # Kon Tum → Quảng Ngãi

            # 12. Gia Lai + Bình Định → Gia Lai (trung tâm Bình Định)
            'VN-31': 'VN-30',  # Bình Định → Gia Lai

            # 13. Khánh Hòa + Ninh Thuận → Khánh Hòa
            'VN-36': 'VN-34',  # Ninh Thuận → Khánh Hòa

            # 14. Lâm Đồng + Đắk Nông + Bình Thuận → Lâm Đồng
            'VN-72': 'VN-35',  # Đắk Nông → Lâm Đồng
            'VN-40': 'VN-35',  # Bình Thuận → Lâm Đồng

            # 15. Đắk Lắk + Phú Yên → Đắk Lắk
            'VN-32': 'VN-33',  # Phú Yên → Đắk Lắk

            # 16. TP.HCM + Bình Dương + Bà Rịa-Vũng Tàu → TP.HCM
            'VN-57': 'VN-SG',  # Bình Dương → TP.HCM
            'VN-43': 'VN-SG',  # Bà Rịa-Vũng Tàu → TP.HCM

            # 17. Đồng Nai + Bình Phước → Đồng Nai
            'VN-58': 'VN-39',  # Bình Phước → Đồng Nai

            # 18. Tây Ninh + Long An → Tây Ninh (trung tâm Long An)
            'VN-41': 'VN-37',  # Long An → Tây Ninh

            # 19. Cần Thơ + Sóc Trăng + Hậu Giang → Cần Thơ
            'VN-52': 'VN-CT',  # Sóc Trăng → Cần Thơ
            'VN-73': 'VN-CT',  # Hậu Giang → Cần Thơ

            # 20. Vĩnh Long + Bến Tre + Trà Vinh → Vĩnh Long
            'VN-50': 'VN-49',  # Bến Tre → Vĩnh Long
            'VN-51': 'VN-49',  # Trà Vinh → Vĩnh Long

            # 21. Đồng Tháp + Tiền Giang → Đồng Tháp (trung tâm Tiền Giang)
            'VN-46': 'VN-45',  # Tiền Giang → Đồng Tháp

            # 22. Cà Mau + Bạc Liêu → Cà Mau
            'VN-55': 'VN-59',  # Bạc Liêu → Cà Mau

            # 23. An Giang + Kiên Giang → An Giang (trung tâm Kiên Giang)
            'VN-47': 'VN-44',  # Kiên Giang → An Giang
        }

        # Get all Vietnam provinces
        all_provinces = self.env['res.country.state'].search([
            ('country_id', '=', vietnam_country_id)
        ])

        # Get partners that need to be migrated
        partners_to_migrate = self.env['res.partner'].search([
            ('state_id', 'in', all_provinces.ids),
            ('state_id.is_vietnam_new_province', '=', False)
        ])

        _logger.info(f"Found {len(partners_to_migrate)} partners to migrate")

        migration_count = 0
        for partner in partners_to_migrate:
            old_state_code = partner.state_id.code
            if old_state_code in migration_mapping:
                new_state_code = migration_mapping[old_state_code]
                new_state = self.env['res.country.state'].search([
                    ('code', '=', new_state_code),
                    ('country_id', '=', vietnam_country_id),
                    ('is_vietnam_new_province', '=', True)
                ], limit=1)

                if new_state:
                    partner.state_id = new_state.id
                    migration_count += 1
                    _logger.info(f"Migrated partner {partner.name} from {old_state_code} to {new_state_code}")

        _logger.info(f"Migration completed. Migrated {migration_count} partners")
        state_archive_ids = self.env['res.country.state'].search([('is_vietnam_new_province', '=', False), ('country_id', '=', vietnam_country_id)])
        for state in state_archive_ids:
            state.active = False
        return True
